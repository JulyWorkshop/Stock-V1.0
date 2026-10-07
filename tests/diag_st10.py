# -*- coding: utf-8 -*-
"""检查页 144 内容"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz
from app.pdf.page_locator import _page_text

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)

print('=== 页 144 全文（前 500 字符）===')
text = _page_text(doc, 143)  # 0-based: 143 = 页 144
print(text[:500])

print('\n=== 页 144 表格 ===')
tables = doc[143].find_tables()
if tables and tables.tables:
    for ti, tbl in enumerate(tables.tables):
        rows = tbl.extract()
        print(f'  表{ti+1} 共 {len(rows)} 行:')
        for ri, row in enumerate(rows[:5]):
            print(f'    行{ri+1}: {row}')
        if len(rows) > 5:
            print(f'    ...(共{len(rows)}行)')

print('\n=== 页 144 含"合并"/"母公司"/"资产负债表" ===')
for kw in ['合并资产负债表', '母公司资产负债表', '资产负债表']:
    if kw in text:
        idx = text.find(kw)
        print(f'  含"{kw}"位置 {idx}，上下文: ...{text[max(0,idx-50):idx+len(kw)+50]}...')

doc.close()
