# -*- coding: utf-8 -*-
"""诊断贵州茅台剩余未识别科目（短期借款）的 PDF 原始值"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz

PDF = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf'
KEY = "短期借款"

doc = fitz.open(PDF)
print(f"PDF: {PDF}")
print(f"总页数: {len(doc)}")
print(f"查找科目: {KEY}")
print("=" * 80)

# 扫描所有页面的表格中是否含"短期借款"
for i in range(len(doc)):
    page = doc[i]
    try:
        tables = page.find_tables()
    except Exception:
        continue
    if not tables or not tables.tables:
        continue
    for ti, tbl in enumerate(tables.tables):
        try:
            rows = tbl.extract()
        except Exception:
            continue
        if not rows:
            continue
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                if cell and KEY in str(cell):
                    print(f"页 {i+1} 表 {ti+1} 行 {ri+1}: {row}")
                    print("-" * 40)

doc.close()
