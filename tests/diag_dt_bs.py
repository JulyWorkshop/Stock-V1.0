# -*- coding: utf-8 -*-
"""诊断大唐药业资产负债表起始页 71 问题"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')
import fitz, re
from app.pdf.page_locator import _page_text, _KNOWN_SUBJECTS, _STRONG_INDICATORS, _FALLBACK_EXCLUDE_KEYWORDS, _get_max_table_rows, _FALLBACK_MIN_TABLE_ROWS

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf'
doc = fitz.open(path)

stmt = '合并资产负债表'
keywords = ['合并资产负债表']
known_subjects = _KNOWN_SUBJECTS[stmt]
strong_indicators = _STRONG_INDICATORS[stmt]
fallback_excludes = _FALLBACK_EXCLUDE_KEYWORDS[stmt]
_re_number = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")

print(f'强标志: {strong_indicators}')
print(f'排除词: {fallback_excludes}')
print()

# 检查页 66-73 的内容
print('=== 页 66-73 分析 ===')
for i in range(65, 73):
    text = _page_text(doc, i)
    title_hit = '合并资产负债表' in text
    has_strong = any(s in text for s in strong_indicators)
    has_excl = any(ex in text[:200] for ex in fallback_excludes)
    hits = [s for s in known_subjects if s in text]
    has_number = _re_number.search(text) is not None
    rows = _get_max_table_rows(doc[i])
    print(f'页{i+1}: 标题={title_hit} 强标志={has_strong} 排除={has_excl} 科目命中={len(hits)}({hits[:5]}) 数值={has_number} 表行={rows}')
    if has_excl:
        excl_hits = [ex for ex in fallback_excludes if ex in text[:200]]
        print(f'  排除词命中: {excl_hits}')
    print(f'  前120字符: {text[:120].replace(chr(10), " | ")}')
    print()

# fallback 候选
print('\n=== fallback 候选页 ===')
fallback_candidates = []
for i in range(len(doc)):
    text = _page_text(doc, i)
    if not text:
        continue
    if strong_indicators and any(s in text for s in strong_indicators):
        text_header = text[:200]
        excluded = any(ex in text_header for ex in fallback_excludes) if fallback_excludes else False
        if excluded:
            continue
        hits = [s for s in known_subjects if s in text]
        if len(hits) >= 3:
            has_number = _re_number.search(text) is not None
            if has_number:
                rows = _get_max_table_rows(doc[i])
                if rows >= _FALLBACK_MIN_TABLE_ROWS:
                    fallback_candidates.append((i+1, len(hits), rows))

fallback_candidates.sort(key=lambda x: x[1], reverse=True)
for p, h, r in fallback_candidates[:10]:
    print(f'  页{p} 科目命中={h} 表行={r}')

if fallback_candidates:
    print(f'\n选中: 页{fallback_candidates[0][0]}')

doc.close()
