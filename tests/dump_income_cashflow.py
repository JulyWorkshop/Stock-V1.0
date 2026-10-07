# -*- coding: utf-8 -*-
"""临时脚本：定位并 dump 利润表和现金流量表的 PDF 页文本，用于编写解析器。"""
import os
import sys

_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pdf_libs")
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fitz
from app.pdf.page_locator import locate_statement_pages


def dump(pdf_path: str, name: str) -> None:
    rng = locate_statement_pages(pdf_path, name)
    print(f"\n========== {name} ==========")
    print(f"页码范围: {rng}")
    if rng is None:
        return
    s, e = rng
    doc = fitz.open(pdf_path)
    try:
        for i in range(s - 1, e):
            if i >= len(doc):
                break
            text = doc[i].get_text("text") or ""
            print(f"\n----- PDF page {i+1} -----")
            print(text[:4000])
    finally:
        doc.close()


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\歌飛\Desktop\价值投资股票财报分析软件\测试年报\中国神华：中国神华2024年度报告.pdf"
    dump(pdf, "合并利润表")
    dump(pdf, "合并现金流量表")
