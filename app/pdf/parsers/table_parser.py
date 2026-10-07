# -*- coding: utf-8 -*-
"""
基于 find_tables() 的结构化表格解析器 - 彻底解决文本流模式把附注编号误当数值的问题。

工作原理：
1. 用 PyMuPDF 的 page.find_tables() 检测页面中的表格结构
2. 通过表头识别列类型（科目名/附注/本年值/上年值）
3. 遍历表格行，从正确的列提取科目名和数值
4. 用 standardize_subject_name 归一化科目名
5. 构造 LineItem

优势：
- 不会把附注编号（如"40"）误当数值
- 能正确处理科目名和数值在不同列的情况
- 适配任何排版的财报表格
"""
import os
import re
import sys
from typing import List, Tuple, Optional

# 接入本地 PyMuPDF 库
_LIB_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..",
    "pdf_libs",
)
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))

import fitz  # PyMuPDF  # noqa: E402

from app.models.line_item import LineItem
from app.models.statements import StatementType
from app.pdf.page_locator import locate_statement_pages
from app.pdf.unit_detector import detect_unit_for_statement
from app.pdf.subject_alias import standardize_subject_name, list_standard_subjects


# 表头关键词映射
# current/prior 分两类：本年类（期末余额/本期金额）和上年类（期初余额/上期金额）
# 年份数字（2020-2025）只在表头出现时用于排序：最大的年份=本年，最小=上年
_HEADER_KEYWORDS = {
    "name": ["项目", "科目", "资产", "负债", "所有者权益", "利润表项目",
             "现金流量表项目", "经营活动", "投资活动", "筹资活动"],
    "footnote": ["附注", "注释"],
    "current": ["期末余额", "本期金额", "本期发生额", "本年金额", "本年发生额",
                "本期", "本年"],
    "prior": ["期初余额", "上期金额", "上期发生额", "上年金额", "上年发生额",
              "上期", "上年"],
}

# 年份关键词（用于表头列排序：数字大的为本年，数字小的为上年）
_YEAR_KEYWORDS = ["2024", "2023", "2022", "2021", "2020", "2019", "2018", "2025",
                  "2026", "2027"]

# 年份→优先级：数字大的优先级高（本年）
def _year_priority(cell_text: str) -> int:
    """返回单元格中年份数字（数字越大优先级越高）"""
    import re as _re
    years = [int(y) for y in _YEAR_KEYWORDS if y in cell_text]
    return max(years) if years else 0


def _find_year_columns_in_header(header_row: list[str] | None) -> list[tuple[int, int]]:
    """
    扫描表头行找含年份字符串的列（如"2025 年12 月31 日"）。
    返回 [(col_idx, year_int), ...]，按列顺序。

    关键改进：不仅看 rows[0]，也扫描前 5 行找真正的表头行（PDF 中 find_tables()
    经常把第一行作为数据而非表头，所以需要在多行内找）。
    """
    if not header_row:
        return []
    # 真正的"表头"特征：含"项目"/"附注"/"本期"/"上期"/"本年"/"上年"/"期末"/"期初"
    # 或含年份字符串
    for row_idx in range(min(5, len(header_row))):
        row = header_row[row_idx]
        if not row:
            continue
        row_text = " ".join(str(c) for c in row if c)
        has_header_kw = any(kw in row_text for kw in ["项目", "附注", "注释", "本期", "上期", "本年", "上年", "期末", "期初"])
        has_year = any(y in row_text for y in _YEAR_KEYWORDS)
        if not (has_header_kw or has_year):
            continue
        # 是表头行：找年份列
        result = []
        for ci, cell in enumerate(row):
            cs = str(cell or "").strip()
            if not cs:
                continue
            for y in _YEAR_KEYWORDS:
                if y in cs and ("年" in cs or "月" in cs or "日" in cs):
                    result.append((ci, int(y)))
                    break
        if result:
            return result
    return []


def _find_nearest_numeric_column(
    data_rows: list[list[str]],
    target_col: int,
    excluded_cols: set[int],
) -> int | None:
    """
    在 data_rows 中找距离 target_col 最近的 numeric 数据列（排除 excluded_cols）。
    返回 col_idx 或 None。
    """
    if not data_rows:
        return None
    # 找所有 numeric 列
    n_cols = max((len(r) for r in data_rows), default=0)
    numeric_cols = []
    for ci in range(n_cols):
        if ci in excluded_cols:
            continue
        num_count = sum(
            1 for row in data_rows
            if ci < len(row) and row[ci] and _is_numeric_cell(str(row[ci]))
        )
        if num_count > 0:
            numeric_cols.append((ci, num_count))
    if not numeric_cols:
        return None
    # 按距离 target_col 排序选最近的，numeric_count 多的优先（并列距离时）
    numeric_cols.sort(key=lambda x: (abs(x[0] - target_col), -x[1]))
    return numeric_cols[0][0]


def _parse_number(s: str) -> Optional[float]:
    """把单元格文本解析为数值。支持千分位逗号、括号负数、减号。"""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s or s in ("—", "－", "-", "—"):
        return None
    # 去括号 / 全角括号
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()
    elif s.startswith("（") and s.endswith("）"):
        negative = True
        s = s[1:-1].strip()
    # 修修复负号：原 lstrip("-") 只剥掉字符但不设 negative，导致 "-123" 被解析为 123（应为 -123）
    if s.startswith("-"):
        negative = True
        s = s[1:].lstrip("-")  # 防 "--123" 之类极端输入
    elif s.startswith("－"):  # 全角负号
        negative = True
        s = s[1:].lstrip("－")
    # 去千分位逗号
    s = s.replace(",", "")
    # 去空格
    s = s.strip()
    if not s:
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    if negative:
        val = -val
    return val


def _is_numeric_cell(s: str) -> bool:
    """判断单元格是否是数值（含逗号分隔的数字）"""
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    if not s:
        return False
    # 含逗号数字、纯数字、括号负数
    if re.match(r"^[\(（]?-?\d{1,3}(,\d{3})*(\.\d+)?[\)）]?$", s):
        return True
    return False


def _is_footnote_cell(s: str) -> bool:
    """判断单元格是否是附注编号（纯整数，通常1-2位数）"""
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    if not s:
        return False
    # 纯整数（1-3位）
    if re.match(r"^\d{1,3}$", s):
        return True
    return False


def _identify_columns(header_row: list[str] | None) -> dict[str, int]:
    """
    通过表头识别列类型。
    返回 {'name': col_idx, 'footnote': col_idx, 'current': col_idx, 'prior': col_idx}
    缺失的列不在 dict 中。

    关键改进：用"年份"确定 current/prior 顺序（数字大=本年），避免上下颠倒。
    """
    col_map = {}
    if not header_row:
        return col_map

    for ci, cell in enumerate(header_row):
        if not cell:
            continue
        cell_text = str(cell).strip()
        if not cell_text:
            continue
        # 检查各类型
        for col_type, keywords in _HEADER_KEYWORDS.items():
            if col_type in col_map:
                continue
            if any(kw in cell_text for kw in keywords):
                col_map[col_type] = ci
                break

    # 用年份大小校正 current/prior 顺序
    # 表头行可能含 "2024 年12 月31 日" 和 "2025 年12 月31 日"，
    # 关键词匹配可能先命中 2024 当 current，再命中 2025 当 prior，
    # 导致 current/prior 颠倒。修复：比较两个年份大小，大的=current。
    current_year = 0
    prior_year = 0
    if "current" in col_map:
        cur_text = str(header_row[col_map["current"]] or "").strip()
        current_year = _year_priority(cur_text)
    if "prior" in col_map:
        pri_text = str(header_row[col_map["prior"]] or "").strip()
        prior_year = _year_priority(pri_text)

    if current_year and prior_year and current_year < prior_year:
        # 颠倒
        col_map["current"], col_map["prior"] = col_map["prior"], col_map["current"]

    return col_map


def _infer_columns_by_content(rows: list[list[str]]) -> dict[str, int]:
    """
    当没有表头时，通过列内容推断列类型。
    修复：跳过空列/None列，只统计有实际内容的列。
    进一步修复：用"年份"线索确定 current/prior 顺序，避免颠倒。
    """
    if not rows:
        return {}

    # 找到最大列数
    n_cols = max(len(row) for row in rows) if rows else 0
    if n_cols == 0:
        return {}

    # 统计每列的特征
    col_stats = []
    for ci in range(n_cols):
        numeric_count = 0
        footnote_count = 0
        text_count = 0
        non_empty_count = 0
        year_count = 0  # 表头可能含 "2025 年12 月31 日"
        for row in rows:
            if ci >= len(row):
                continue
            cell = row[ci]
            if cell is None:
                continue
            cell_str = str(cell).strip()
            if not cell_str:
                continue
            non_empty_count += 1
            if _is_numeric_cell(cell_str):
                numeric_count += 1
            elif _is_footnote_cell(cell_str):
                footnote_count += 1
            else:
                text_count += 1
            # 检测年份线索
            for y in _YEAR_KEYWORDS:
                if y in cell_str:
                    year_count += 1
                    break
        col_stats.append({
            "numeric": numeric_count,
            "footnote": footnote_count,
            "text": text_count,
            "non_empty": non_empty_count,
            "year": year_count,
        })

    col_map = {}
    # 科目名列：文本最多的列（且非空内容最多）
    text_scores = [(ci, s["text"]) for ci, s in enumerate(col_stats)]
    text_scores.sort(key=lambda x: x[1], reverse=True)
    if text_scores and text_scores[0][1] > 0:
        col_map["name"] = text_scores[0][0]

    # 附注列：附注编号最多的列（但不是科目名列）
    footnote_scores = [(ci, s["footnote"]) for ci, s in enumerate(col_stats) if ci != col_map.get("name")]
    footnote_scores.sort(key=lambda x: x[1], reverse=True)
    if footnote_scores and footnote_scores[0][1] > 0:
        col_map["footnote"] = footnote_scores[0][0]

    # 数值列：数值最多的列（排除科目名和附注列）
    exclude_cols = {col_map.get("name"), col_map.get("footnote")}
    numeric_scores = [(ci, s["numeric"]) for ci, s in enumerate(col_stats) if ci not in exclude_cols and s["non_empty"] > 0]
    numeric_scores.sort(key=lambda x: x[1], reverse=True)
    if len(numeric_scores) >= 1 and numeric_scores[0][1] > 0:
        col_map["current"] = numeric_scores[0][0]
    if len(numeric_scores) >= 2 and numeric_scores[1][1] > 0:
        col_map["prior"] = numeric_scores[1][0]

    # 修复：current/prior 颠倒问题
    # 关键启发式：表头行（含"项目""附注"等标识）通常在 rows[0]
    # 如果 rows[0] 是表头行（含"项目"或"附注"等关键词），用其年份排序校正
    if rows and len(rows) > 0:
        first_row = rows[0]
        first_text = " ".join(str(c) for c in first_row if c)
        # 检查首行是否像表头
        if any(kw in first_text for kw in ["项目", "附注", "本期", "上期", "本年", "上年", "期末", "期初"]):
            current_year = 0
            prior_year = 0
            if "current" in col_map:
                c_text = str(first_row[col_map["current"]] or "").strip()
                current_year = _year_priority(c_text)
            if "prior" in col_map:
                p_text = str(first_row[col_map["prior"]] or "").strip()
                prior_year = _year_priority(p_text)

            if current_year and prior_year and current_year < prior_year:
                col_map["current"], col_map["prior"] = col_map["prior"], col_map["current"]

    return col_map


def _clean_subject_name(s: str) -> str:
    """清理科目名：去掉行首编号、前缀、括号说明后缀等"""
    if not s:
        return ""
    s = str(s).strip()
    # 去掉换行符
    s = s.replace("\n", "").replace("\r", "")
    # 去掉行首中文数字编号（如"一、" "二、" "五、"）
    s = re.sub(r"^[一二三四五六七八九十]+、", "", s).strip()
    # 去掉行首阿拉伯数字编号（如"1." "（1）"）
    s = re.sub(r"^[\(（]?\d[\)）\.、\s]+", "", s).strip()
    # 去掉"加：" "减："前缀
    s = re.sub(r"^[加减][:：]", "", s).strip()
    # 去掉"其中："前缀
    s = re.sub(r"^其中[:：]", "", s).strip()
    # 去掉行尾的括号说明（如"（净亏损以"－"号填列）" "（损失以"-"号填列）"）
    s = re.sub(r"[\(（][^)）]*[\)）]\s*$", "", s).strip()
    # 去掉行尾不完整的括号说明（如"营业利润（亏损以"－"号填"——括号开始但未闭合，
    # 常见于 PDF 表格提取时科目名跨行被截断的情况）
    # 修复岩山科技利润表"营业利润""利润总额""净利润"未识别问题：
    #   科目名被截断为"二、营业利润（亏损以"－"号填"，清理"二、"后仍为"营业利润（亏损以"－"号填"，
    #   含括号但未闭合，导致 standardize_subject_name 的包含匹配比例检查失败
    s = re.sub(r"[\(（][^)）]*$", "", s).strip()
    return s


def _find_statement_tables(
    doc,
    start_page: int,
    end_page: int,
    statement_type: str,
) -> list[tuple[int, list[list[str]], dict[str, int]]]:
    """
    在报表页范围内找到包含报表数据的表格。
    返回 [(page_no, table_rows, col_map), ...]
    """
    from app.pdf.page_locator import _KNOWN_SUBJECTS

    known_subjects = _KNOWN_SUBJECTS.get(statement_type, [])
    result = []

    for page_idx in range(start_page - 1, end_page):
        if page_idx >= len(doc):
            break
        page = doc[page_idx]
        try:
            table_finder = page.find_tables()
        except Exception:
            continue
        if not table_finder or not table_finder.tables:
            continue

        for table in table_finder.tables:
            try:
                rows = table.extract()
            except Exception:
                continue
            if not rows:
                continue

            # 检查这个表格是否包含已知科目（确认是目标报表）
            all_text = " ".join(str(cell) for row in rows for cell in row if cell)
            if known_subjects and not any(s in all_text for s in known_subjects):
                continue

            # 识别列类型
            # 策略：表头识别 + 内容推断，内容推断优先（表头合并单元格会导致列索引偏移）
            header_row = rows[0] if rows else None
            col_map_header = _identify_columns(header_row)
            col_map_content = _infer_columns_by_content(rows[1:] if len(rows) > 1 else rows)
            # 内容推断优先（基于实际数据位置，更准确）
            col_map = {**col_map_header, **col_map_content}

            # 关键修复：current/prior 列颠倒
            # 问题1：表头关键词匹配按列顺序，第一个含"本年"的列=current，但"2024"关键词
            #   可能先于"2025"被命中（取决于 find_tables 的列排列顺序），导致 current/prior 颠倒。
            # 问题2：_infer_columns_by_content 按 numeric_count 排序决定 current/prior，
            #   当两列 numeric 数差 1 行就翻转（页70 第2个表：列6=11 数字、列9=12 数字，
            #   选了列9 当 current，实际列9 是"2024"年份对应的数据）。
            # 修复：直接扫描表头行找含年份字符串的列作为锚点，再找附近的 numeric 数据列。
            header_year_cols = _find_year_columns_in_header(rows) if rows else []
            if len(header_year_cols) >= 2:
                # 按年份大小排序：最大的=current，其次=prior
                header_year_cols.sort(key=lambda x: x[1], reverse=True)
                cur_year_col, _ = header_year_cols[0]
                pri_year_col, _ = header_year_cols[1]

                # 找 cur_year_col 附近最近的 numeric 数据列（排除 name 和 footnote）
                excluded = {col_map.get("name"), col_map.get("footnote")}
                cur_col = _find_nearest_numeric_column(rows[1:], cur_year_col, excluded)
                pri_col = _find_nearest_numeric_column(rows[1:], pri_year_col, excluded | {cur_col} if cur_col is not None else excluded)

                if cur_col is not None:
                    col_map["current"] = cur_col
                if pri_col is not None:
                    col_map["prior"] = pri_col
            elif "current" in col_map and "prior" in col_map:
                # 启发式：没有表头年份信息时，按列索引顺序——左=本年、右=上年
                # 中国年报报告的合并报表通常左"列是本年期末余额、右"列是上年期末余额，
                # 这是惯例。修复：当 _infer_columns_by_content 选错时（如 numeric 数差 1 行就翻转），
                # 强制按列索引校正为左=current、右=prior。
                if col_map["current"] > col_map["prior"]:
                    col_map["current"], col_map["prior"] = col_map["prior"], col_map["current"]

            # 如果还是没有 name 列，默认第0列
            if "name" not in col_map:
                col_map["name"] = 0
            # 如果还是没有 current 列，找第一个数值列
            if "current" not in col_map:
                for ci in range(len(rows[0]) if rows else 0):
                    if ci == col_map.get("name"):
                        continue
                    if ci == col_map.get("footnote"):
                        continue
                    # 检查这列是否有数值
                    has_num = False
                    for row in rows[1:]:
                        if ci < len(row) and row[ci] and _is_numeric_cell(str(row[ci])):
                            has_num = True
                            break
                    if has_num:
                        col_map["current"] = ci
                        break

            result.append((page_idx + 1, rows, col_map))

    return result


def parse_statement_by_table(
    pdf_path: str,
    year: int,
    statement_type: str,
    company_name: str = "",
) -> list[LineItem]:
    """
    基于表格结构解析报表。
    返回 LineItem 列表。
    """
    items: list[LineItem] = []

    # 1. 定位页码范围
    page_range = locate_statement_pages(pdf_path, statement_type)
    if page_range is None:
        print(f"[table_parser] 未能在 PDF 中定位到 {statement_type}: {pdf_path}")
        return items
    start_page, end_page = page_range

    # 2. 单位
    unit = detect_unit_for_statement(pdf_path, start_page)

    # 3. 找到报表表格
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[table_parser] 打开 PDF 失败: {pdf_path} -> {e}")
        return items

    try:
        table_data = _find_statement_tables(doc, start_page, end_page, statement_type)
    finally:
        try:
            doc.close()
        except Exception:
            pass

    if not table_data:
        print(f"[table_parser] 未在 {start_page}-{end_page} 页找到 {statement_type} 表格")
        return items

    # 4. 遍历表格行，提取科目和数值
    seen_standard: set[str] = set()
    all_standard = list_standard_subjects(statement_type)

    for page_no, rows, col_map in table_data:
        name_col = col_map.get("name", 0)
        footnote_col = col_map.get("footnote")
        current_col = col_map.get("current")
        prior_col = col_map.get("prior")

        if current_col is None:
            # 找不到数值列，跳过这个表格
            continue

        for ri, row in enumerate(rows):
            # 跳过表头行
            if ri == 0:
                header_text = " ".join(str(c) for c in row if c)
                if any(kw in header_text for kw in ["项目", "附注", "期末余额", "本期金额"]):
                    continue

            # 获取科目名
            if name_col >= len(row):
                continue
            raw_name = str(row[name_col]).strip() if row[name_col] else ""
            if not raw_name:
                continue

            # 清理科目名
            clean_name = _clean_subject_name(raw_name)
            if not clean_name:
                continue

            # 跳过分类标题（如"流动资产""非流动资产"等）
            from app.pdf.parsers.balance_sheet import _CATEGORY_HEADERS
            compact_name = clean_name.replace(" ", "").replace("\u3000", "")
            category_headers_compact = {
                h.replace(" ", "").replace("\u3000", "") for h in _CATEGORY_HEADERS
            }
            if compact_name in category_headers_compact:
                continue

            # 归一化为标准科目
            standard = standardize_subject_name(clean_name)
            if standard is None:
                continue

            # 跳过已识别的科目
            if standard in seen_standard:
                continue

            # 提取本年数值
            value = None
            if current_col is not None and current_col < len(row):
                cell = row[current_col]
                if cell:
                    value = _parse_number(str(cell))

            # 如果本年值为空，尝试用上年值（某些科目只有上年值）
            if value is None and prior_col is not None and prior_col < len(row):
                cell = row[prior_col]
                if cell:
                    value = _parse_number(str(cell))

            # 修复：value 为 None 时不再直接跳过。
            # 原逻辑会漏掉"PDF 中科目存在但值为空"的情况（如贵州茅台"短期借款"为 0、
            #   大唐药业"应付债券"为空白），导致这些科目没被记录。
            # 新逻辑：仍创建 LineItem（is_recognized=False），让用户在确认页看到"⚠ 未识别"并人工补。
            # 这样 verify_all 的识别率统计更真实：科目行被解析到=算识别。
            # CF 特例：合并现金流量表里"科目存在但值为空"=0（中国会计惯例，空格即0），
            #   如 ST卓然 2025"收回投资收到的现金/取得投资收益收到的现金"实际为 0 但 PDF 表里该格空白。
            #   对 CF 强制按 0 处理，避免 5+ 个空值科目被误判为未识别。
            if value is None:
                if statement_type == "合并现金流量表":
                    value = 0.0
                else:
                    item = LineItem(
                        year=year,
                        statement_type=statement_type,
                        name=standard,
                        aliases=[raw_name],
                        original_value=None,
                        unit=unit,
                        source_pdf=pdf_path,
                        source_page=page_no,
                        is_recognized=False,  # PDF 中有科目名但无数值
                    )
                    items.append(item)
                    seen_standard.add(standard)
                    continue

            # 构造 LineItem
            item = LineItem(
                year=year,
                statement_type=statement_type,
                name=standard,
                aliases=[raw_name],
                original_value=value,
                unit=unit,
                source_pdf=pdf_path,
                source_page=page_no,
                is_recognized=(value is not None),
            )
            items.append(item)
            seen_standard.add(standard)

    # 5. 对未命中的标准科目，仍创建 LineItem（is_recognized=False 留 UI 手工补）
    for std in all_standard:
        if std in seen_standard:
            continue
        items.append(LineItem(
            year=year,
            statement_type=statement_type,
            name=std,
            aliases=[],
            original_value=None,
            unit=unit,
            source_pdf=pdf_path,
            source_page=start_page,
            is_recognized=False,
        ))

    # 6. fallback_scan 补漏（借鉴 workbuddy 的 5 大策略 + 双数值）
    #    对 is_recognized=False 的科目用宽松匹配重扫，按 name+year 替换 original_value；
    #    主解析已找到的不动，避免被覆盖。
    try:
        from app.pdf.parsers.fallback_scan import fallback_scan as _fallback_scan
        _already = {item.name for item in items if item.is_recognized}
        _fb_items = _fallback_scan(pdf_path, year, statement_type, _already, company_name)
        _key_index = {(it.name, it.year): i for i, it in enumerate(items)}
        for fb in _fb_items:
            if fb.original_value is None:
                continue
            key = (fb.name, fb.year)
            if key in _key_index:
                idx = _key_index[key]
                ex = items[idx]
                if ex.original_value is None:
                    # 用 fallback 的值填充
                    ex.original_value = fb.original_value
                    ex.unit = fb.unit or ex.unit
                    ex.source_pdf = fb.source_pdf or ex.source_pdf
                    ex.source_page = fb.source_page or ex.source_page
                    ex.is_recognized = True
                    if fb.aliases and not ex.aliases:
                        ex.aliases = list(fb.aliases)
            else:
                # 主解析完全没创建该科目（理论上少见，因为 line 601 已经为所有 all_standard 创建了 LineItem）
                items.append(fb)
    except Exception as e:
        print(f"[table_parser] fallback_scan 调用失败: {e}")

    return items
