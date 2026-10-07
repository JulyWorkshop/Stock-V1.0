# -*- coding: utf-8 -*-
"""诊断贵州茅台应收账款缺失问题"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')
import fitz
from app.pdf.page_locator import locate_statement_pages, _page_text
from app.pdf.subject_alias import standardize_subject_name
from app.pdf.parsers.table_parser import _clean_subject_name

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf'
doc = fitz.open(path)

r = locate_statement_pages(path, '合并资产负债表')
print(f'资产负债表页范围: {r}')

# 1. 搜索所有页面中含"应收"的页面
print('\n=== 所有页面中含"应收"的页面（页 50-57）===')
for i in range(49, 57):
    text = _page_text(doc, i)
    if '应收' in text:
        # 找所有"应收"出现的位置
        idx = 0
        while True:
            idx = text.find('应收', idx)
            if idx == -1:
                break
            ctx = text[max(0,idx-10):idx+20].replace('\n', ' | ')
            print(f'  页{i+1} 位置{idx}: ...{ctx}...')
            idx += 2

# 2. 检查页 52-56 表格中含"应收"的行
print('\n=== 页 52-56 表格中含"应收"的行 ===')
for page_idx in range(51, 56):
    page = doc[page_idx]
    try:
        table_finder = page.find_tables()
    except Exception:
        continue
    if not table_finder or not table_finder.tables:
        continue
    for tbl_idx, table in enumerate(table_finder.tables):
        try:
            rows = table.extract()
        except Exception:
            continue
        if not rows:
            continue
        for ri, row in enumerate(rows):
            row_text = ' '.join(str(c) for c in row if c)
            if '应收' in row_text:
                print(f'  页{page_idx+1} 表{tbl_idx+1} 行{ri+1}: {row}')
                for ci, cell in enumerate(row):
                    if cell and '应收' in str(cell):
                        raw = str(cell).strip()
                        clean = _clean_subject_name(raw)
                        std = standardize_subject_name(clean)
                        print(f'    列{ci} 原文="{raw}" 清理后="{clean}" 标准名="{std}"')

# 3. 检查页 53 前 500 字符（之前的起始页）
print('\n=== 页 53 前 500 字符 ===')
text53 = _page_text(doc, 52)
print(text53[:500].replace('\n', ' | '))

doc.close()
