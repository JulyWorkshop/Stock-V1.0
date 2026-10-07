# -*- coding: utf-8 -*-
"""
解析合并利润表，提取所有标准科目。

接口：
    parse_income_statement(pdf_path, year, company_name) -> list[LineItem]

流程：
1. 调用 page_locator.locate_statement_pages 定位页码
2. 调用 unit_detector.detect_unit_for_statement 取单位
3. 逐页 get_text("text") 拼接大文本
4. 按行扫描，调用 standardize_subject_name() 归一化
5. 处理"加：/减："前缀、"一、二、三"行首编号、科目名含括号说明
6. 命中标准科目后从该行（或下一行）提取数字（期末余额=第一列数值）
7. 跳过"其中："子项与附注编号行
8. 构造 LineItem
"""
import os
import re
import sys

# 接入本地 PyMuPDF 库
# 本文件位于 ffa/app/pdf/parsers/，比 app/pdf/ 下文件深一级，需 ../../../../
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


# 利润表分类标题（不是科目，应跳过）
_CATEGORY_HEADERS = {
    # 按经营持续性分类等小标题
    "按经营持续性分类", "按所有权归属分类",
    "不能重分类进损益的其他综合收益", "将重分类进损益的其他综合收益",
    "归属于母公司股东的其他综合收益的税后净额",
    # 每股收益下的标题
    "每股收益",
    # 子合计行（防误识）
    "归属于母公司股东的其他综合收益的税后净额合计",
    # 占位
    "合计", "总计", "小计",
}

# "加：/减："前缀
_RE_PREFIX = re.compile(r"^[加减][:：]")

# 行首编号："一、二、三、四、五、六、七、八、九、十" 或 "1." "2." "（1）"
_RE_CHINESE_NUM = re.compile(r"^[一二三四五六七八九十]+、")
_RE_ARABIC_NUM = re.compile(r"^[\(（]?\d[\)）\.、\s]+")

# 科目名尾随括号说明（如"投资收益 (损失以"-"号填列)"）——去掉括号及说明
_RE_TRAILING_PAREN = re.compile(r"\s*[\(（][^)）]*[\)）]\s*$")

# 无数据标记：单独 "-"、"-*"、"—"
_RE_NO_DATA = re.compile(r"^[—\-－\*\s]+$")

# 其他综合收益明细项中的"公允价值变动"型子项（如"其他权益工具投资公允价值变动"）
# 这些不是科目，是其他综合收益的明细项，应跳过
_RE_OCI_DETAIL = re.compile(r"公允价值变动|折算差额|权益法下.*其他综合收益")


def _strip_subject_line(line: str) -> str:
    """去掉行首"加：/减："前缀和"一、二、"编号，去掉尾随括号说明。"""
    if not line:
        return ""
    s = line.strip()
    # 去"加：/减："前缀
    s = _RE_PREFIX.sub("", s).strip()
    # 去中文数字编号"一、"
    s = _RE_CHINESE_NUM.sub("", s).strip()
    # 去阿拉伯数字编号"1." "（1）"
    s = _RE_ARABIC_NUM.sub("", s).strip()
    # 去尾随括号说明
    s = _RE_TRAILING_PAREN.sub("", s).strip()
    return s


def _strip_subitem_prefix(line: str) -> str:
    """去掉"其中："前缀（用于利润表中"其中：利息费用"等真科目的识别）"""
    if not line:
        return ""
    s = line.strip()
    return _RE_SUBITEM.sub("", s).strip()


def parse_income_statement(
    pdf_path: str,
    year: int,
    company_name: str,
) -> list[LineItem]:
    """解析合并利润表，返回 LineItem 列表。"""
    items: list[LineItem] = []
    statement_type = StatementType.INCOME_STATEMENT.value

    # 1. 定位页码范围
    page_range = locate_statement_pages(pdf_path, statement_type)
    if page_range is None:
        print(f"[income_statement] 未能在 PDF 中定位到 {statement_type}: {pdf_path}")
        return items
    start_page, end_page = page_range

    # 2. 单位
    unit = detect_unit_for_statement(pdf_path, start_page)

    # 3. 提取所有页文本
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[income_statement] 打开 PDF 失败: {pdf_path} -> {e}")
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
            # 跳过无数据标记行
            if _RE_NO_DATA.match(line):
                idx += 1
                continue
            # 跳过附注编号行
            if _RE_FOOTNOTE.match(line):
                idx += 1
                continue
            # "其中："子项处理：
            # - 若去掉"其中："后能归一化为标准科目（如"其中：利息费用"→"利息费用"），保留
            # - 否则跳过（普通子项）
            is_subitem = bool(_RE_SUBITEM.match(line))
            if is_subitem:
                stripped = _strip_subitem_prefix(line)
                stripped = _strip_subject_line(stripped)
                if standardize_subject_name(stripped) is None:
                    # 不是标准科目，跳过
                    idx += 1
                    continue
                # 是标准科目，继续处理
                line_for_match = stripped
            else:
                # 去前缀/编号/尾随括号
                line_for_match = _strip_subject_line(line)
            if not line_for_match:
                idx += 1
                continue
            # 跳过分类标题
            compact = line_for_match.replace(" ", "").replace("\u3000", "")
            if compact in {h.replace(" ", "").replace("\u3000", "") for h in _CATEGORY_HEADERS}:
                idx += 1
                continue
            # 跳过其他综合收益明细项（如"其他权益工具投资公允价值变动"）
            if _RE_OCI_DETAIL.search(line_for_match) and "损益" not in line_for_match:
                idx += 1
                continue
            # 归一化为标准科目
            standard = standardize_subject_name(line_for_match)
            if standard is None:
                idx += 1
                continue
            if standard in seen_standard:
                idx += 1
                continue
            # 提取期末余额
            alias_used = None
            for alias in [standard, line_for_match]:
                if alias and alias in line:
                    alias_used = alias
                    break
            if alias_used is None:
                if line_for_match.replace(" ", "").replace("\u3000", "") in line.replace(" ", "").replace("\u3000", ""):
                    alias_used = line_for_match
            residual = _strip_subject_from_line(line, alias_used) if alias_used else line
            value = _extract_first_value_from_line(residual)

            # 策略2：本行无数值，向后看后续行
            if value is None:
                look_ahead = min(idx + 5, line_count)
                for j in range(idx + 1, look_ahead):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if _RE_FOOTNOTE.match(next_line):
                        continue
                    if _RE_NO_DATA.match(next_line):
                        continue
                    # 下一行是另一科目名，停止
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
            idx += 1

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
