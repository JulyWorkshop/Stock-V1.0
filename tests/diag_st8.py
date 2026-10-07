# -*- coding: utf-8 -*-
"""检查页 152 现金流量表 fallback 是否被加入"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz
from app.pdf.page_locator import (
    _page_text, _KNOWN_SUBJECTS, _FALLBACK_EXCLUDE_KEYWORDS,
    _get_max_table_rows, _FALLBACK_MIN_TABLE_ROWS, _STRONG_INDICATORS,
)

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)

# 检查页 152 和 153
print('=== 检查页 152 和 153 现金流量表状态 ===')
stmt = '合并现金流量表'
known = _KNOWN_SUBJECTS[stmt]
strong = _STRONG_INDICATORS[stmt]
excludes = _FALLBACK_EXCLUDE_KEYWORDS[stmt]

print(f'强标志: {strong}')
print(f'排除词: {excludes}')
print(f'最低表格行数: {_FALLBACK_MIN_TABLE_ROWS}')

for pi in [151, 152]:  # 页 152 和 153 (0-based: 151, 152)
    text = _page_text(doc, pi)
    hits = [s for s in known if s in text]
    strong_hits = [s for s in strong if s in text]
    excl_hits = [ex for ex in excludes if ex in text]
    max_rows = _get_max_table_rows(doc[pi])
    print(f'\n页{pi+1}:')
    print(f'  命中科目: {hits} ({len(hits)}个)')
    print(f'  命中强标志: {strong_hits}')
    print(f'  命中排除词: {excl_hits}')
    print(f'  最大表格行数: {max_rows}')
    print(f'  应入 fallback_candidates? '
          f'{"是" if strong_hits and len(hits) >= 3 and not excl_hits and max_rows >= _FALLBACK_MIN_TABLE_ROWS else "否"}')

# 看页 152 的文本是否真含"母公司现金流量表"
text_152 = _page_text(doc, 151)
print('\n=== 页 152 是否含"母公司"相关字符串 ===')
for s in ['母公司', '母公司现金流量表', '母公司利润表', '母公司资产负债表']:
    if s in text_152:
        # 找出出现位置
        idx = text_152.find(s)
        context = text_152[max(0, idx-30):idx+len(s)+30]
        print(f'  含"{s}"，上下文: ...{context}...')

doc.close()
