# -*- coding: utf-8 -*-
"""
诊断多公司"资产总计"未识别问题。
检查每家公司资产负债表页面中"资产总计"的原文形式和表格提取结果。
"""
import sys
import os

sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz
from app.pdf.page_locator import locate_statement_pages, _page_text
from app.pdf.subject_alias import standardize_subject_name, SUBJECT_ALIASES_BY_STATEMENT

# 5 家测试公司 PDF 路径（使用正确的路径）
PDFS = {
    'ST卓然': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf',
    '大唐药业': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf',
    '贵州茅台': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf',
    '天键股份': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\1ebd8903-d4f6-410e-873a-25e36b1cc605_58c3aff0-bb5d-4f19-96af-8b36d1a8bac0_天键股份：2025年年度报告（更正后）.pdf',
    '岩山科技': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\91132a2d-d9f0-4907-bdca-6664b8f56b52_075d5e45-a1da-4258-aa6b-7307074a9136_岩山科技：2025年年度报告（更正后）.pdf',
}

# 资产负债表的所有"总资产"别名
TOTAL_ASSETS_ALIASES = SUBJECT_ALIASES_BY_STATEMENT['合并资产负债表'].get('总资产', [])
print(f'总资产的标准名: "总资产"')
print(f'总资产的别名: {TOTAL_ASSETS_ALIASES}')
print(f'standardize_subject_name("资产总计") = {standardize_subject_name("资产总计")}')
print(f'standardize_subject_name("总资产") = {standardize_subject_name("总资产")}')
print(f'standardize_subject_name("资产合计") = {standardize_subject_name("资产合计")}')
print()

# 找一家存在的 PDF 测试
for name, path in PDFS.items():
    if not os.path.exists(path):
        print(f'[{name}] PDF 不存在: {path}')
        continue

    print(f'\n{"=" * 60}')
    print(f'【{name}】')
    print(f'{"=" * 60}')

    try:
        doc = fitz.open(path)
    except Exception as e:
        print(f'  打开失败: {e}')
        continue

    # 定位资产负债表页码
    page_range = locate_statement_pages(path, '合并资产负债表')
    if page_range is None:
        print(f'  未定位到合并资产负债表')
        doc.close()
        continue

    start_page, end_page = page_range
    print(f'  资产负债表页范围: ({start_page}, {end_page})')

    # 扫描所有页面，找含"资产总计""资产合计""总资产"的页面
    print(f'\n  --- 含"资产总计"/"资产合计"/"总资产"的页面 ---')
    for i in range(len(doc)):
        text = _page_text(doc, i)
        for kw in ['资产总计', '资产合计', '总资产']:
            if kw in text:
                # 找上下文
                idx = text.find(kw)
                ctx_start = max(0, idx - 20)
                ctx_end = min(len(text), idx + len(kw) + 50)
                ctx = text[ctx_start:ctx_end].replace('\n', ' | ')
                print(f'    页{i+1} 含"{kw}" 上下文: ...{ctx}...')
                break

    # 提取所有页面的表格，找"资产总计"行
    print(f'\n  --- 资产负债表页范围内的表格中含"资产总计"的行 ---')
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
                # 找含"资产总计"或"资产合计"的行
                for kw in ['资产总计', '资产合计', '总资产']:
                    if kw in row_text:
                        print(f'    页{page_idx+1} 表{tbl_idx+1} 行{ri+1}: {row}')
                        # 测试 standardize_subject_name
                        # 找name列（第一列有内容的）
                        for ci, cell in enumerate(row):
                            if cell and kw in str(cell):
                                clean = str(cell).strip().replace('\n', '').replace('\r', '')
                                std = standardize_subject_name(clean)
                                print(f'      列{ci} 原文="{clean}" -> 标准名="{std}"')
                                break
                        break

    doc.close()

print('\n完成')
