# -*- coding: utf-8 -*-
"""
解析合并现金流量表，提取所有标准科目。

接口：
    parse_cash_flow(pdf_path, year, company_name) -> list[LineItem]

流程：
1. 调用 page_locator.locate_statement_pages 定位页码
2. 调用 unit_detector.detect_unit_for_statement 取单位
3. 逐页 get_text("text") 拼接大文本
4. 按行扫描，调用 standardize_subject_name() 归一化
5. 处理"一、二、三、四、五、六"活动分类编号
6. 处理多行科目名（如"处置固定资产、无形资产和其他\n长期资产收回的现金净额"）
7. 括号负数、"—"无数据标记
8. 跳过"其中："子项与附注编号
9. 构造 LineItem
"""
import os
import re
import sys

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
from app.pdf.parsers.balance_sheet import (
    _parse_number_token,
    _extract_first_value_from_line,
    _strip_subject_from_line,
    _RE_FOOTNOTE,
    _RE_SUBITEM,
)


# 现金流量表三大活动分类标题（不是科目，应跳过）
_CATEGORY_HEADERS = {
    "经营活动产生的现金流量",
    "投资活动产生的现金流量",
    "筹资活动产生的现金流量",
    # 占位
    "合计", "总计",
}

# "一、二、三" 行首编号
_RE_CHINESE_NUM = re.compile(r"^[一二三四五六七八九十]+、")
# "1." "2." "（1）" 行首编号
_RE_ARABIC_NUM = re.compile(r"^[\(（]?\d[\)）\.、\s]+")

# 多行科目名拼接：检测是否是科目名的延续行（不以编号开头、无数字、与已知科目名前缀匹配）
# 当科目名跨行时，需要把下一行拼到当前行末尾再归一化

# 无数据标记
_RE_NO_DATA = re.compile(r"^[—\-－\*\s]+$")


def _strip_subject_line(line: str) -> str:
    """去掉行首"一、二、"等编号和"1."等编号。"""
    if not line:
        return ""
    s = line.strip()
    s = _RE_CHINESE_NUM.sub("", s).strip()
    s = _RE_ARABIC_NUM.sub("", s).strip()
    return s


def _try_merge_multiline(lines: list[str], idx: int, current_subject: str) -> tuple[str, int]:
    """
    尝试把多行科目名拼接成一行（如"处置固定资产、无形资产和其他\n长期资产收回的现金净额"）。

    输入：lines=所有行，idx=下一行索引，current_subject=已扫描到的科目名前缀。
    返回：(拼接后的科目名, 消耗的行数)。
    如果未能拼接，返回 (current_subject, 0)。
    """
    merged = current_subject
    consumed = 0
    j = idx
    # 最多尝试 3 行
    for _ in range(3):
        if j >= len(lines):
            break
        next_line = lines[j].strip()
        if not next_line:
            j += 1
            consumed += 1
            continue
        # 下一行含数字 → 是数值行，不是科目名延续
        if re.search(r"\d", next_line):
            break
        # 下一行是另一科目名或分类标题 → 停止
        next_compact = _strip_subject_line(next_line)
        if next_compact and standardize_subject_name(next_compact) is not None:
            break
        # 下一行是"其中："子项 → 停止
        if _RE_SUBITEM.match(next_line):
            break
        # 下一行是附注编号 → 跳过
        if _RE_FOOTNOTE.match(next_line):
            j += 1
            consumed += 1
            continue
        # 拼接到当前科目名
        merged = merged + next_line.strip()
        j += 1
        consumed += 1
        # 尝试归一化拼接后的名字
        if standardize_subject_name(merged) is not None:
            # 找到完整科目名
            return merged, consumed
    # 没拼出完整科目名，回退
    return current_subject, 0


def parse_cash_flow(
    pdf_path: str,
    year: int,
    company_name: str,
) -> list[LineItem]:
    """解析合并现金流量表，返回 LineItem 列表。"""
    items: list[LineItem] = []
    statement_type = StatementType.CASH_FLOW_STATEMENT.value

    # 1. 定位页码范围
    page_range = locate_statement_pages(pdf_path, statement_type)
    if page_range is None:
        print(f"[cash_flow] 未能在 PDF 中定位到 {statement_type}: {pdf_path}")
        return items
    start_page, end_page = page_range

    # 2. 单位
    unit = detect_unit_for_statement(pdf_path, start_page)

    # 3. 提取所有页文本
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[cash_flow] 打开 PDF 失败: {pdf_path} -> {e}")
        return items

    page_chunks: list[tuple[int, str]] = []
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
        return items

    # 4. 标准科目集合
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
            # 跳过无数据标记行
            if _RE_NO_DATA.match(line):
                idx += 1
                continue
            # 跳过附注编号行
            if _RE_FOOTNOTE.match(line):
                idx += 1
                continue
            # 跳过"其中："子项
            if _RE_SUBITEM.match(line):
                idx += 1
                continue
            # 去行首编号
            line_for_match = _strip_subject_line(line)
            if not line_for_match:
                idx += 1
                continue
            # 跳过分类标题
            compact = line_for_match.replace(" ", "").replace("\u3000", "")
            if compact in {h.replace(" ", "").replace("\u3000", "") for h in _CATEGORY_HEADERS}:
                idx += 1
                continue
            # 归一化
            standard = standardize_subject_name(line_for_match)
            # 尝试多行科目名拼接
            consumed_extra = 0
            if standard is None:
                merged, consumed = _try_merge_multiline(lines, idx + 1, line_for_match)
                if merged != line_for_match:
                    line_for_match = merged
                    standard = standardize_subject_name(line_for_match)
                    consumed_extra = consumed
            if standard is None:
                idx += 1
                continue
            if standard in seen_standard:
                idx += 1 + consumed_extra
                continue

            # 提取期末余额（第一列数值）
            alias_used = None
            for alias in [standard, line_for_match]:
                if alias and alias in line:
                    alias_used = alias
                    break
            if alias_used is None:
                # 用拼接后的科目名作为 alias
                if line_for_match.replace(" ", "").replace("\u3000", "") in line.replace(" ", "").replace("\u3000", ""):
                    alias_used = line_for_match
            residual = _strip_subject_from_line(line, alias_used) if alias_used else line
            value = _extract_first_value_from_line(residual)

            # 策略2：本行无数值，向后看后续行（处理多行科目名 + 数值分行）
            if value is None:
                look_ahead = min(idx + 5 + consumed_extra, line_count)
                start_j = idx + 1 + consumed_extra
                for j in range(start_j, look_ahead):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if _RE_FOOTNOTE.match(next_line):
                        continue
                    if _RE_NO_DATA.match(next_line):
                        continue
                    # 下一行是另一科目名 → 停止
                    next_match = _strip_subject_line(next_line)
                    if next_match and standardize_subject_name(next_match) is not None:
                        break
                    if _RE_SUBITEM.match(next_line):
                        continue
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
            idx += 1 + consumed_extra

    # 6. 对未命中的标准科目，仍创建 LineItem
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
