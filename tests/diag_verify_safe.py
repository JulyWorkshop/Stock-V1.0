# -*- coding: utf-8 -*-
"""快速检查 ST 卓然关键页面前 200 字符是否含排除词"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')
import fitz
from app.pdf.page_locator import _page_text

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)

exclude_words = ['变动原因', '利润构成', '本期比上年', '母公司利润表', '母公司现金流量表', '母公司资产负债表']

for p in [145, 146, 147, 148, 152, 153]:
    text = _page_text(doc, p-1)
    header = text[:200]
    hits = [w for w in exclude_words if w in header]
    print(f'页{p} 排除词命中: {hits if hits else "无"}')
    if hits:
        print(f'  前200字符: {header[:200]}')

doc.close()
