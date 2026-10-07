# -*- coding: utf-8 -*-
"""调试 _find_statement_start_page 内部状态"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import re
import fitz
from app.pdf.page_locator import (
    _page_text, _KNOWN_SUBJECTS, _STRONG_INDICATORS,
    _FALLBACK_EXCLUDE_KEYWORDS, _get_max_table_rows, _FALLBACK_MIN_TABLE_ROWS,
)

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)

_re_number = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")
audit_keywords = ["审计报告", "保留意见", "无法表示意见", "拒绝表示意见",
    "否定意见", "天职业字", "会计师事务所", "审计范围限制",
    "审计证据", "替代性程序", "项目合伙人", "中国注册会计师"]


def debug_fallback(stmt_type):
    print(f'\n=== {stmt_type} 调试 ===')
    known = _KNOWN_SUBJECTS[stmt_type]
    strong = _STRONG_INDICATORS[stmt_type]
    excludes = _FALLBACK_EXCLUDE_KEYWORDS[stmt_type]
    print(f'强标志: {strong}')
    print(f'排除词: {excludes}')
    print(f'最低表格行数: {_FALLBACK_MIN_TABLE_ROWS}')
    print(f'已知科目: {known}')

    candidates = []
    for i in range(len(doc)):
        text = _page_text(doc, i)
        if not text:
            continue
        if not any(s in text for s in strong):
            continue
        hits = [s for s in known if s in text]
        if len(hits) < 3:
            continue
        if not _re_number.search(text):
            continue
        # 排除词检查
        excluded_by = [ex for ex in excludes if ex in text]
        max_rows = _get_max_table_rows(doc[i])
        candidates.append((i + 1, len(hits), max_rows, excluded_by, hits))

    print(f'\n所有候选（强标志+3科目+数值）共 {len(candidates)} 个:')
    for page, n, rows, excl, hits in candidates:
        status = '✅' if (rows >= _FALLBACK_MIN_TABLE_ROWS and not excl) else '❌'
        reason = []
        if rows < _FALLBACK_MIN_TABLE_ROWS:
            reason.append(f'行数不足({rows}<{_FALLBACK_MIN_TABLE_ROWS})')
        if excl:
            reason.append(f'含排除词{excl}')
        print(f'  页{page}: 命中{n}科目, 表格{rows}行, {status} {("原因: " + "; ".join(reason)) if reason else ""}')
        print(f'    命中: {hits}')


for stmt in ['合并资产负债表', '合并利润表', '合并现金流量表']:
    debug_fallback(stmt)

doc.close()
