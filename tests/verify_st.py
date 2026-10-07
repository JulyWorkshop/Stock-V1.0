# -*- coding: utf-8 -*-
"""验证 ST 卓然三大表数据提取"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

from app.pdf.parsers.table_parser import parse_statement_by_table

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'

# 关键科目 - 使用标准科目名（subject_alias.py 中的 key）
# "资产总计"是别名，标准名是"总资产"；"负债合计"是别名，标准名是"总负债"
# "所有者权益合计"不是标准名，用"归属于母公司所有者权益"替代
KEY_SUBJECTS = {
    '合并资产负债表': ['货币资金', '应收账款', '存货', '固定资产', '短期借款', '应付账款',
                   '总负债', '实收资本', '资本公积', '未分配利润',
                   '归属于母公司所有者权益', '总资产'],
    '合并利润表': ['营业收入', '营业成本', '营业利润', '利润总额', '净利润', '管理费用', '销售费用'],
    '合并现金流量表': ['经营活动', '投资活动', '筹资活动', '现金流量净额', '现金及现金等价物'],
}


for stmt_type, keys in KEY_SUBJECTS.items():
    print(f'\n=== {stmt_type} ===')
    items = parse_statement_by_table(path, 2025, stmt_type, 'ST卓然')
    print(f'识别到 {len(items)} 个科目')
    rec_count = sum(1 for it in items if it.is_recognized)
    print(f'其中已识别: {rec_count}')

    # 找出关键科目
    found = {}
    for it in items:
        if it.is_recognized:
            for k in keys:
                if k in it.name or it.name in k:
                    found[k] = it
                    break

    print(f'\n关键科目识别情况:')
    for k in keys:
        if k in found:
            it = found[k]
            v = it.value
            val_str = f'值={v:,.2f}' if v is not None else '未识别(None)'
            print(f'  ✅ {k}: {val_str} (页{it.source_page})')
        else:
            print(f'  ❌ {k}: 未识别')
