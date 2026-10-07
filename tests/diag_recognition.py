# -*- coding: utf-8 -*-
"""验证 5 个测试公司三大表识别情况（含值正确性检查）"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

from app.pdf.parsers.table_parser import parse_statement_by_table
from app.pdf.page_locator import locate_statement_pages

TEST_CASES = [
    ('ST卓然', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf', 2025),
    ('大唐药业', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf', 2025),
    ('贵州茅台', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf', 2018),
    ('天键股份', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\1ebd8903-d4f6-410e-873a-25e36b1cc605_58c3aff0-bb5d-4f19-96af-8b36d1a8bac0_天键股份：2025年年度报告（更正后）.pdf', 2025),
    ('岩山科技', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\91132a2d-d9f0-4907-bdca-6664b8f56b52_075d5e45-a1da-4258-aa6b-7307074a9136_岩山科技：2025年年度报告（更正后）.pdf', 2025),
]

KEY_SUBJECTS = {
    '合并资产负债表': ['货币资金', '应收账款', '存货', '短期借款', '应付账款', '实收资本', '资本公积', '未分配利润', '总资产'],
    '合并利润表': ['营业收入', '营业成本', '营业利润', '利润总额', '净利润', '管理费用', '销售费用'],
    '合并现金流量表': ['经营活动产生的现金流量净额', '销售商品提供劳务收到的现金'],
}


def check(name, path, year):
    print(f'\n{"="*70}')
    print(f'【{name}】 {year} 年报')
    print("="*70)
    total_rec = 0
    total_count = 0
    for stmt_type, keys in KEY_SUBJECTS.items():
        page_range = locate_statement_pages(path, stmt_type)
        if page_range is None:
            print(f'  {stmt_type}: ❌ 未定位到')
            continue
        items = parse_statement_by_table(path, year, stmt_type, name)
        # 用 LineItem 的 is_recognized 和 original_value != None 判断
        rec_items = [it for it in items if it.is_recognized]
        rec_count = len(rec_items)
        total_count += len(items)
        total_rec += rec_count

        # 关键科目值检查
        val_check = []
        for k in keys:
            for it in rec_items:
                if it.name == k:
                    val_check.append((k, it.original_value, it.source_page))
                    break
            else:
                val_check.append((k, None, None))

        print(f'  {stmt_type} {page_range}: {rec_count}/{len(items)}')
        for k, v, p in val_check:
            if v is None:
                print(f'    ⚠ {k:20}=未识别')
            else:
                print(f'    ✓ {k:20}={v:>20,.2f} (p{p})')

    print(f'  --- 总计: {total_rec}/{total_count} ---')


for name, path, year in TEST_CASES:
    check(name, path, year)