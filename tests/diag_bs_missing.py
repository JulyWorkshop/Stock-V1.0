# -*- coding: utf-8 -*-
"""
诊断资产负债表缺失科目问题。
检查每家公司资产负债表页面中缺失科目的原文形式和表格提取结果。
"""
import sys
import os

sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz
from app.pdf.page_locator import locate_statement_pages, _page_text
from app.pdf.subject_alias import standardize_subject_name
from app.pdf.parsers.table_parser import _clean_subject_name, _is_numeric_cell

PDFS = {
    '大唐药业': (r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf', ['货币资金', '应收账款', '存货']),
    '贵州茅台': (r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf', ['短期借款', '应付账款']),
    '天键股份': (r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\1ebd8903-d4f6-410e-873a-25e36b1cc605_58c3aff0-bb5d-4f19-96af-8b36d1a8bac0_天键股份：2025年年度报告（更正后）.pdf', ['短期借款']),
    '岩山科技': (r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\91132a2d-d9f0-4907-bdca-6664b8f56b52_075d5e45-a1da-4258-aa6b-7307074a9136_岩山科技：2025年年度报告（更正后）.pdf', ['应收账款', '存货', '短期借款']),
}

for company, (path, missing_subjects) in PDFS.items():
    print(f'\n{"=" * 60}')
    print(f'【{company}】 缺失科目: {missing_subjects}')
    print(f'{"=" * 60}')

    doc = fitz.open(path)
    page_range = locate_statement_pages(path, '合并资产负债表')
    if page_range is None:
        print('  未定位到资产负债表')
        doc.close()
        continue

    start_page, end_page = page_range
    print(f'  资产负债表页范围: ({start_page}, {end_page})')

    # 1. 检查页面文本中是否含缺失科目
    print(f'\n  --- 页面文本中含缺失科目的位置 ---')
    for ms in missing_subjects:
        found_in_text = False
        for i in range(start_page - 1, end_page):
            text = _page_text(doc, i)
            if ms in text:
                idx = text.find(ms)
                ctx = text[max(0, idx-30):idx+len(ms)+30].replace('\n', ' | ')
                print(f'    "{ms}" 在页{i+1}文本中: ...{ctx}...')
                found_in_text = True
        if not found_in_text:
            # 搜索全部页面
            for i in range(len(doc)):
                text = _page_text(doc, i)
                if ms in text and (i+1 < start_page or i+1 > end_page):
                    print(f'    "{ms}" 在页{i+1}（范围外）')
                    found_in_text = True
                    break
            if not found_in_text:
                print(f'    "{ms}" 在所有页面都未找到')

    # 2. 检查表格中含缺失科目的行
    print(f'\n  --- 表格中含缺失科目的行 ---')
    for page_idx in range(start_page - 1, end_page):
        if page_idx >= len(doc):
            break
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
                for ms in missing_subjects:
                    if ms in row_text:
                        print(f'    页{page_idx+1} 表{tbl_idx+1} 行{ri+1}: {row}')
                        # 找name列
                        for ci, cell in enumerate(row):
                            if cell and ms in str(cell):
                                raw = str(cell).strip()
                                clean = _clean_subject_name(raw)
                                std = standardize_subject_name(clean)
                                print(f'      列{ci} 原文="{raw}" 清理后="{clean}" 标准名="{std}"')
                        # 找数值列
                        for ci, cell in enumerate(row):
                            if cell and _is_numeric_cell(str(cell)):
                                print(f'      列{ci} 数值="{cell}"')
                        break

    doc.close()

print('\n完成')
