# -*- coding: utf-8 -*-
"""诊断脚本：对一份 PDF 跑三大表解析器，打印识别率与关键科目数值。

用法：
    python -m tests.diag_all <pdf_path> [year]
"""
import os
import sys

_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pdf_libs")
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pdf.parsers.balance_sheet import parse_balance_sheet
from app.pdf.parsers.income_statement import parse_income_statement
from app.pdf.parsers.cash_flow import parse_cash_flow
from app.pdf.subject_alias import list_standard_subjects


def _print_summary(items, label: str) -> None:
    recognized = [it for it in items if it.is_recognized]
    print(f"\n========== {label} ==========")
    print(f"已识别: {len(recognized)}/{len(items)}")
    print("--- 已识别科目 ---")
    for it in recognized:
        print(f"  {it.name:<30} = {it.original_value:>15}  (p{it.source_page})")
    print("--- 未识别科目 ---")
    recognized_names = {it.name for it in recognized}
    for std in list_standard_subjects(label):
        if std in recognized_names:
            continue
        print(f"  {std}")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python -m tests.diag_all <pdf_path> [year]")
        return 2
    pdf_path = sys.argv[1]
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    if not os.path.isfile(pdf_path):
        print(f"文件不存在: {pdf_path}")
        return 2

    print(f"PDF: {pdf_path}")
    print(f"Year: {year}")

    bs = parse_balance_sheet(pdf_path, year, "")
    _print_summary(bs, "合并资产负债表")

    ic = parse_income_statement(pdf_path, year, "")
    _print_summary(ic, "合并利润表")

    cf = parse_cash_flow(pdf_path, year, "")
    _print_summary(cf, "合并现金流量表")

    return 0


if __name__ == "__main__":
    sys.exit(main())
