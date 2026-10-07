# -*- coding: utf-8 -*-
"""检查页 146 和 147 的营业收入位置"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz
from app.pdf.page_locator import _page_text

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)

# 看 146, 147 页全文
for pi in [145, 146]:  # 页 146 和 147 (0-based: 145, 146)
    text = _page_text(doc, pi)
    print(f'\n=== 页{pi+1} 全文 ===')
    print(text)
    print(f'\n--- 页{pi+1} 表格 ---')
    tables = doc[pi].find_tables()
    if tables and tables.tables:
        for ti, tbl in enumerate(tables.tables):
            rows = tbl.extract()
            print(f'  表{ti+1} 共 {len(rows)} 行')
            for ri, row in enumerate(rows[:5]):  # 只看前5行
                print(f'    行{ri+1}: {row}')
            if len(rows) > 5:
                print(f'    ...(共{len(rows)}行)')

doc.close()
