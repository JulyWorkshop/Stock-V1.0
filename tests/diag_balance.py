# -*- coding: utf-8 -*-
"""
诊断脚本：直接调用 parse_balance_sheet 并打印每个科目的识别情况、
未识别原因、定位页码与单位。用于排查"科目大面积未识别"问题。

用法：
    python -m tests.diag_balance <pdf_path> [year]
"""
import os
import sys

# 接入本地 PyMuPDF 库
_LIB_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..",
    "pdf_libs",
)
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))

# 让 ffa 包可被导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fitz  # noqa: E402

from app.pdf.page_locator import locate_statement_pages  # noqa: E402
from app.pdf.unit_detector import detect_unit_for_statement  # noqa: E402
from app.pdf.parsers.balance_sheet import parse_balance_sheet  # noqa: E402
from app.pdf.subject_alias import list_standard_subjects, standardize_subject_name  # noqa: E402


def dump_page_text(pdf_path: str, start_page: int, end_page: int, max_chars: int = 4000) -> None:
    """打印定位区间的前若干字符，便于人工核对页面内容。"""
    doc = fitz.open(pdf_path)
    try:
        print(f"\n===== 页 {start_page}-{end_page} 文本预览（前 {max_chars} 字符） =====")
        printed = 0
        for i in range(start_page - 1, end_page):
            if i >= len(doc):
                break
            text = doc[i].get_text("text") or ""
            print(f"\n----- PDF page {i+1} (index {i}) -----")
            head = text[:max_chars - printed]
            print(head)
            printed += len(head)
            if printed >= max_chars:
                break
    finally:
        doc.close()


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python -m tests.diag_balance <pdf_path> [year]")
        return 2
    pdf_path = sys.argv[1]
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    if not os.path.isfile(pdf_path):
        print(f"文件不存在: {pdf_path}")
        return 2

    print(f"PDF: {pdf_path}")
    print(f"Year: {year}")
    print(f"文件大小: {os.path.getsize(pdf_path):,} bytes")

    # 1) 定位
    page_range = locate_statement_pages(pdf_path, "合并资产负债表")
    print(f"\n[定位] 合并资产负债表页码范围: {page_range}")
    if page_range is None:
        print("定位失败，结束。")
        return 1
    start_page, end_page = page_range
    print(f"  起始页: {start_page}, 结束页: {end_page}, 共 {end_page - start_page + 1} 页")

    # 2) 单位
    unit = detect_unit_for_statement(pdf_path, start_page)
    print(f"[单位] 识别为: {unit}")

    # 3) 解析
    items = parse_balance_sheet(pdf_path, year, "中国神华")
    print(f"\n[解析] 共返回 {len(items)} 个 LineItem")

    recognized = [it for it in items if it.is_recognized]
    unrecognized = [it for it in items if not it.is_recognized]
    print(f"  已识别: {len(recognized)}")
    print(f"  未识别: {len(unrecognized)}")

    # 4) 已识别科目清单
    print("\n----- 已识别 -----")
    for it in recognized:
        print(f"  {it.name:<20} = {it.original_value:>20}  (来源 p{it.source_page})")

    # 5) 未识别科目清单
    print("\n----- 未识别 -----")
    all_std = list_standard_subjects("合并资产负债表")
    for std in all_std:
        if std in {it.name for it in recognized}:
            continue
        print(f"  {std}")

    # 6) 打印定位页文本预览，便于人工核对
    dump_page_text(pdf_path, start_page, end_page, max_chars=6000)

    return 0


if __name__ == "__main__":
    sys.exit(main())
