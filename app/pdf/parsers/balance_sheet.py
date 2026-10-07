# -*- coding: utf-8 -*-
"""
解析合并资产负债表，提取所有标准科目。

接口：
    parse_balance_sheet(pdf_path, year, company_name) -> list[LineItem]

流程：
1. 调用 page_locator.locate_statement_pages 定位页码
2. 找不到返回空列表，并 print 警告
3. 调用 unit_detector.detect_unit_for_statement 取单位
4. 逐页 get_text("text") 拼接大文本
5. 按行扫描，调用 standardize_subject_name() 归一化
6. 命中标准科目后从该行（或下一行）提取数字
7. 括号或"-"表示负数
8. 只取期末余额（第一列数值）
9. 构造 LineItem
10. 未识别的科目跳过
11. 找不到数值的标准科目，仍创建 LineItem 但 original_value=None, is_recognized=False
"""
import os
import re
import sys

# 接入本地 PyMuPDF 库
# 注意：本文件位于 ffa/app/pdf/parsers/，比 app/pdf/ 下文件深一级，需 ../../../../
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


# 分类标题（不是科目，应跳过）——含分区标题和子合计行，不含"资产总计/负债合计"
# 注意："资产总计""负债合计"等是科目（有数值），不能放这里跳过
# 子合计行（如"流动资产合计"）必须跳过，否则会被 standardize_subject_name 的
# 包含匹配逻辑误识为"总资产"（"流动资产合计"含"资产合计"4字）
_CATEGORY_HEADERS = {
    "流动资产", "非流动资产",
    "流动负债", "非流动负债",
    "股东权益", "负债和股东权益",
    # 子合计行
    "流动资产合计", "非流动资产合计",
    "流动负债合计", "非流动负债合计",
    "股东权益合计", "负债和股东权益合计", "负债和股东权益总计",
}

# 附注编号正则：如 "五、1" "十六、2" "五、47(1)" "附注"
# 支持带括号子编号（如"五、47(1)"表示第 47 号附注的第 1 个子项）
_RE_FOOTNOTE = re.compile(
    r"^[一二三四五六七八九十]+、\d+(?:[\(（]\d+[\)）])?$"
    r"|^附注$"
    r"|^[一二三四五六七八九十]+$"  # 单独章节号"五""十六"
)

# "其中：" 开头的子项，不是独立科目
_RE_SUBITEM = re.compile(r"^其中[:：]")

# 数值匹配正则：
# - 千分位逗号: 1,234,567.89
# - 括号表示负数: (1,234.56) 或 （1,234.56）
# - 减号: -1,234.56
# - "—" 或 "－" 表示无数据
# 数字 token：
_NUM_TOKEN = r"(?:\(|\（)?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\)|\))?"
# 简化的行内数字提取：去掉科目名后剩余部分
_RE_NUMBERS_IN_LINE = re.compile(
    r"(?P<sign>[(（-])?\s*(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?)[)）]?"
)
# 无数据标记
_RE_NO_DATA = re.compile(r"^[—\-－\s]+$")


def _parse_number_token(raw: str) -> float | None:
    """把单段数字 token 转为 float。"""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    # 去括号 / 全角括号
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    elif s.startswith("（") and s.endswith("）"):
        negative = True
        s = s[1:-1]
    s = s.lstrip("-")
    if not s:
        return None
    # 千分位逗号去掉
    s = s.replace(",", "")
    try:
        val = float(s)
    except ValueError:
        return None
    if negative:
        val = -val
    return val


def _extract_first_value_from_line(line: str) -> float | None:
    """
    从行文本中提取第一个有效数值（期末余额）。
    行格式可能是："  货币资金  12,345,678.90  11,111,111.11"
    也可能是单值或带括号负数。
    找不到返回 None。
    """
    if not line:
        return None
    # 无数据标记
    if _RE_NO_DATA.match(line):
        return None
    # 找所有数值 token
    matches = list(_RE_NUMBERS_IN_LINE.finditer(line))
    for m in matches:
        num_str = m.group("num")
        # 判断符号是否在 token 旁
        sign = m.group("sign")
        token = num_str
        if sign:
            token = sign + num_str + (")" if sign == "(" else ("）" if sign == "（" else ""))
        val = _parse_number_token(token)
        if val is not None:
            return val
    return None


def _strip_subject_from_line(line: str, subject_alias: str) -> str:
    """
    从行文本中删除科目名（含别名）部分，返回剩余（用于数字提取）。
    保守处理：只删除第一次出现的别名，剩下部分作为数字列。
    """
    if not line or not subject_alias:
        return line
    idx = line.find(subject_alias)
    if idx < 0:
        # 尝试去除空白后匹配
        compact_line = line.replace(" ", "").replace("\u3000", "")
        compact_alias = subject_alias.replace(" ", "").replace("\u3000", "")
        idx_c = compact_line.find(compact_alias)
        if idx_c < 0:
            return line
        # 重建对应位置：粗暴做法——返回 compact_line 截断后的部分
        return compact_line[idx_c + len(compact_alias):]
    return line[idx + len(subject_alias):]


def parse_balance_sheet(
    pdf_path: str,
    year: int,
    company_name: str,
) -> list[LineItem]:
    """
    解析合并资产负债表，返回 LineItem 列表。
    """
    items: list[LineItem] = []
    statement_type = StatementType.BALANCE_SHEET.value

    # 1. 定位页码范围
    page_range = locate_statement_pages(pdf_path, statement_type)
    if page_range is None:
        print(f"[balance_sheet] 未能在 PDF 中定位到 {statement_type}: {pdf_path}")
        return items
    start_page, end_page = page_range

    # 2. 单位
    unit = detect_unit_for_statement(pdf_path, start_page)

    # 3. 提取所有页文本，并保留页码标记
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[balance_sheet] 打开 PDF 失败: {pdf_path} -> {e}")
        return items

    page_chunks: list[tuple[int, str]] = []  # (1-based page_no, text)
    try:
        for i in range(start_page - 1, end_page):
            if i >= len(doc):
                break
            try:
                page_text = doc[i].get_text("text") or ""
            except Exception:
                page_text = ""
            page_chunks.append((i + 1, page_text))
    finally:
        try:
            doc.close()
        except Exception:
            pass

    if not page_chunks:
        print(f"[balance_sheet] 报表页范围内无可读文本: {pdf_path}")
        return items

    # 4. 标准科目集合（用于未识别补建）
    all_standard = list_standard_subjects(statement_type)
    seen_standard: set[str] = set()

    # 5. 逐页、逐行扫描
    for page_no, text in page_chunks:
        if not text:
            continue
        lines = text.splitlines()
        line_count = len(lines)
        idx = 0
        while idx < line_count:
            line = lines[idx].strip()
            if not line:
                idx += 1
                continue
            # 跳过分类标题
            if line.replace(" ", "").replace("\u3000", "") in {
                h.replace(" ", "").replace("\u3000", "") for h in _CATEGORY_HEADERS
            }:
                idx += 1
                continue
            # 跳过"其中："子项
            if _RE_SUBITEM.match(line):
                idx += 1
                continue
            # 跳过附注编号行
            if _RE_FOOTNOTE.match(line):
                idx += 1
                continue
            # 去掉行首的项目编号（如 "1"、"1."、"（1）"）
            line_for_match = re.sub(r"^[\(（]?\d[\)）\.、\s]+", "", line).strip()
            if not line_for_match:
                idx += 1
                continue
            # 归一化为标准科目
            standard = standardize_subject_name(line_for_match)
            if standard is None:
                idx += 1
                continue
            if standard in seen_standard:
                # 同一报表内只取首次命中
                idx += 1
                continue
            # 提取期末余额：
            # 策略1：先尝试从本行提取（科目名和数字在同一行的情况）
            alias_used = None
            for alias in [standard, line_for_match]:
                if alias and alias in line:
                    alias_used = alias
                    break
            if alias_used is None:
                if line_for_match in line:
                    alias_used = line_for_match
                else:
                    if line_for_match.replace(" ", "").replace("\u3000", "") in line.replace(" ", "").replace("\u3000", ""):
                        alias_used = line_for_match
            residual = _strip_subject_from_line(line, alias_used) if alias_used else line
            value = _extract_first_value_from_line(residual)

            # 策略2：如果本行没有数字，向前看后续行（处理科目名和数字在不同行的情况）
            if value is None:
                look_ahead = min(idx + 5, line_count)
                for j in range(idx + 1, look_ahead):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    # 跳过附注编号行
                    if _RE_FOOTNOTE.match(next_line):
                        continue
                    # 如果下一行是另一个科目名，停止搜索
                    next_match = re.sub(r"^[\(（]?\d[\)）\.、\s]+", "", next_line).strip()
                    if next_match and standardize_subject_name(next_match) is not None:
                        break
                    # 跳过"其中："子项
                    if _RE_SUBITEM.match(next_line):
                        continue
                    # 尝试从该行提取数字
                    value = _extract_first_value_from_line(next_line)
                    if value is not None:
                        break

            # 构造 LineItem
            item = LineItem(
                year=year,
                statement_type=statement_type,
                name=standard,
                aliases=[line],
                original_value=value,
                unit=unit,
                source_pdf=pdf_path,
                source_page=page_no,
                is_recognized=(value is not None),
            )
            items.append(item)
            seen_standard.add(standard)
            idx += 1

    # 6. 对未命中的标准科目，仍创建 LineItem（original_value=None, is_recognized=False）
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

    return items
