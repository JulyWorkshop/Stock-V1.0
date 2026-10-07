# -*- coding: utf-8 -*-
"""
从年报文本中识别金额单位（元 / 千元 / 万元 / 百万元 / 亿元）。

接口：
- detect_unit(text: str) -> str
- detect_unit_for_statement(pdf_path: str, start_page: int) -> str
"""
import os
import re
import sys

# 接入本地 PyMuPDF 库
_LIB_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..",
    "pdf_libs",
)
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))

import fitz  # PyMuPDF  # noqa: E402

from app.config import Unit


# 单位关键词 → Unit 字符串
# 顺序很重要：百万元 要先于 元 检查；万元 要先于 元 检查
# 支持 "金额单位：人民币百万元" 等变体（人民币前缀、金额前缀、括号包裹）
_UNIT_PATTERNS = [
    (Unit.HUNDRED_MILLION_YUAN, re.compile(r"单位\s*[:：]\s*(?:人民币)?\s*亿\s*元")),
    (Unit.MILLION_YUAN,          re.compile(r"单位\s*[:：]\s*(?:人民币)?\s*百万\s*元")),
    (Unit.TEN_THOUSAND_YUAN,     re.compile(r"单位\s*[:：]\s*(?:人民币)?\s*万\s*元")),
    (Unit.THOUSAND_YUAN,         re.compile(r"单位\s*[:：]\s*(?:人民币)?\s*千\s*元")),
    (Unit.YUAN,                  re.compile(r"单位\s*[:：]\s*(?:人民币)?\s*元")),
]


def detect_unit(text: str) -> str:
    """
    从文本（通常是报表表头附近）识别单位。
    返回 Unit.YUAN/THOUSAND_YUAN/TEN_THOUSAND_YUAN/MILLION_YUAN/HUNDRED_MILLION_YUAN 之一。
    找不到返回 Unit.YUAN（默认假设元，UI 会显示让用户复核）。

    实现思路：
    - 搜索"单位：元" / "单位：千元" / "单位：万元" / "单位：百万元" / "单位：亿元"
    - 注意全角半角冒号、空格差异
    """
    if not text:
        return Unit.YUAN
    # 把全角冒号归一为半角，便于匹配
    normalized = text.replace("\uff1a", ":")
    for unit_value, pattern in _UNIT_PATTERNS:
        if pattern.search(normalized):
            return unit_value
    return Unit.YUAN


def detect_unit_for_statement(pdf_path: str, start_page: int) -> str:
    """
    定位到报表页后，从该页文本前 500 字符提取单位。
    start_page 为 1-based 页码。
    若 start_page 越界或失败，默认返回 Unit.YUAN。
    """
    if not pdf_path or start_page is None or start_page < 1:
        return Unit.YUAN
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[unit_detector] 打开 PDF 失败: {pdf_path} -> {e}")
        return Unit.YUAN

    try:
        page_index = start_page - 1  # 转 0-based
        if page_index >= len(doc):
            return Unit.YUAN
        text = doc[page_index].get_text("text") or ""
        # 取前 500 字符（表头通常在前面）
        head = text[:500]
        return detect_unit(head)
    except Exception as e:
        print(f"[unit_detector] 读取页文本失败: {pdf_path} p{start_page} -> {e}")
        return Unit.YUAN
    finally:
        try:
            doc.close()
        except Exception:
            pass
