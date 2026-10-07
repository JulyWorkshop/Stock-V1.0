# -*- coding: utf-8 -*-
"""调试 _find_statement_start_page 内部 fallback_candidates 内容"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import re
import fitz
from app.pdf.page_locator import (
    _page_text, _KNOWN_SUBJECTS, _STATEMENT_START_KEYWORDS,
    _STRONG_INDICATORS, _FALLBACK_EXCLUDE_KEYWORDS,
    _get_max_table_rows, _FALLBACK_MIN_TABLE_ROWS,
)

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)

_re_number = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")
audit_keywords = ["审计报告", "保留意见", "无法表示意见", "拒绝表示意见",
    "否定意见", "天职业字", "会计师事务所", "审计范围限制",
    "审计证据", "替代性程序", "项目合伙人", "中国注册会计师"]
header_hints = ["期末余额", "期初余额", "本期金额", "上期金额",
    "本期发生额", "上期发生额", "本年金额", "上年金额",
    "金额单位", "附注"]


def trace_fallback(stmt_type):
    print(f'\n=== {stmt_type} 跟踪 ===')
    keywords = _STATEMENT_START_KEYWORDS.get(stmt_type, [stmt_type])
    known_subjects = _KNOWN_SUBJECTS.get(stmt_type, [])
    strong_indicators = _STRONG_INDICATORS.get(stmt_type, [])
    fallback_excludes = _FALLBACK_EXCLUDE_KEYWORDS.get(stmt_type, [])

    last_hit_page = None
    fallback_candidates = []

    for i in range(len(doc)):
        text = _page_text(doc, i)
        if not text:
            continue
        title_hit = any(kw in text for kw in keywords)
        if title_hit:
            if any(akw in text for akw in audit_keywords):
                print(f'  页{i+1}: title_hit 但含审计词，continue（跳过 fallback 块）')
                continue
            has_number = _re_number.search(text) is not None
            if not has_number:
                print(f'  页{i+1}: title_hit 但无数值，continue（跳过 fallback 块）')
                continue
            has_header = any(h in text for h in header_hints)
            has_strong = any(s in text for s in strong_indicators)
            if has_header and known_subjects and any(s in text for s in known_subjects) and has_strong:
                print(f'  页{i+1}: 强匹配，直接 return')
                return i + 1
            if has_header and has_strong:
                print(f'  页{i+1}: 中匹配，直接 return')
                return i + 1
            if has_strong:
                max_rows = _get_max_table_rows(doc[i])
                if max_rows >= _FALLBACK_MIN_TABLE_ROWS:
                    last_hit_page = i + 1
                    print(f'  页{i+1}: title_hit + has_strong + 表格{max_rows}行 → last_hit_page={last_hit_page}')

        # fallback 块
        if strong_indicators and any(s in text for s in strong_indicators):
            if fallback_excludes and any(ex in text for ex in fallback_excludes):
                continue
            if known_subjects:
                subject_hits_list = [s for s in known_subjects if s in text]
                if len(subject_hits_list) >= 3:
                    has_number = _re_number.search(text) is not None
                    if has_number:
                        max_rows = _get_max_table_rows(doc[i])
                        if max_rows >= _FALLBACK_MIN_TABLE_ROWS:
                            fallback_candidates.append((i + 1, len(subject_hits_list)))
                            print(f'  页{i+1}: 加入 fallback_candidates (命中{len(subject_hits_list)}科目, 表格{max_rows}行)')

    print(f'\n  最终: last_hit_page={last_hit_page}, fallback_candidates={fallback_candidates}')
    if fallback_candidates:
        fallback_candidates.sort(key=lambda x: x[1], reverse=True)
        result = fallback_candidates[0][0]
        print(f'  返回 fallback_candidates[0]={result}')
        return result
    print(f'  返回 last_hit_page={last_hit_page}')
    return last_hit_page


for stmt in ['合并资产负债表', '合并利润表', '合并现金流量表']:
    trace_fallback(stmt)

doc.close()
