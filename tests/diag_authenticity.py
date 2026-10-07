# -*- coding: utf-8 -*-
"""诊断真实性检测：验证5项真实性指标的科目识别与计算结果
重点确认：未识别科目是否被错误地当作0处理，导致假阳性高风险
"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

from app.pdf.parsers.table_parser import parse_statement_by_table
from app.pdf.page_locator import locate_statement_pages
from app.models.line_item import LineItem
from app.models.project import AnalysisProject
from app.models.company import Company
from app.calculation import formulas
from app.rules.engine import _classify_status
from app.models.rule import RuleStatus

# 贵州茅台 2018
NAME = '贵州茅台'
PATH = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf'
YEAR = 2018

# 真实性检测的5个规则 ID
AUTH_RULES = [
    'auth_cash_interest_yield',
    'auth_prepayment_ratio',
    'auth_prepay_other_receivable',
    'auth_cash_receipt_ratio',
    'auth_net_profit_cash_ratio',
]

# 每个规则引用的科目（与 engine.py _EVIDENCE_SUBJECTS 一致）
RULE_SUBJECTS = {
    'auth_cash_interest_yield': [('利息收入', '合并利润表'), ('货币资金', '合并资产负债表')],
    'auth_prepayment_ratio': [('预付款项', '合并资产负债表'), ('总资产', '合并资产负债表')],
    'auth_prepay_other_receivable': [('预付款项', '合并资产负债表'), ('其他应收款', '合并资产负债表'), ('总资产', '合并资产负债表')],
    'auth_cash_receipt_ratio': [('销售商品提供劳务收到的现金', '合并现金流量表'), ('营业收入', '合并利润表')],
    'auth_net_profit_cash_ratio': [('经营活动产生的现金流量净额', '合并现金流量表'), ('净利润', '合并利润表')],
}

# 公式函数映射（与 engine.py _FORMULA_MAP 一致）
FORMULA_MAP = {
    'auth_cash_interest_yield': formulas.cash_interest_yield,
    'auth_prepayment_ratio': formulas.prepayment_ratio,
    'auth_prepay_other_receivable': formulas.prepay_plus_other_receivable_ratio,
    'auth_cash_receipt_ratio': formulas.cash_receipt_ratio,
    'auth_net_profit_cash_ratio': formulas.net_profit_cash_ratio,
}


def build_project():
    """解析贵州茅台三大表，构造 AnalysisProject"""
    company = Company(name=NAME, stock_code='600519')
    project = AnalysisProject(company=company)
    line_items = []
    for stmt in ['合并资产负债表', '合并利润表', '合并现金流量表']:
        page_range = locate_statement_pages(PATH, stmt)
        if page_range is None:
            print(f'  ❌ {stmt} 未定位到')
            continue
        items = parse_statement_by_table(PATH, YEAR, stmt, NAME)
        print(f'  {stmt} {page_range}: {sum(1 for it in items if it.is_recognized)}/{len(items)} 已识别')
        line_items.extend(items)
    project.line_items = line_items
    return project


def main():
    print(f'\n{"="*70}')
    print(f'【{NAME}】 {YEAR} 年报 - 真实性检测诊断')
    print("="*70)

    project = build_project()

    print(f'\n{"="*70}')
    print('5 项真实性检测科目识别与计算')
    print("="*70)

    for rid in AUTH_RULES:
        print(f'\n--- {rid} ---')
        # 1. 检查科目识别情况
        subjects = RULE_SUBJECTS[rid]
        for name, stmt in subjects:
            li = project.get_line_item(YEAR, name, stmt)
            if li is None:
                print(f'  ❌ 科目未识别: {name} ({stmt})')
            elif li.original_value is None:
                print(f'  ⚠ 科目识别但值为空: {name} ({stmt}), original_value=None')
            else:
                val = li.safe_value_in_yuan
                print(f'  ✅ {name} ({stmt}): {val:,.2f} 元 (source_page={li.source_page})')

        # 2. 用 get_safe_value_in_yuan 取值（未识别返回0）
        print('  [get_safe_value_in_yuan 取值]')
        for name, stmt in subjects:
            v = project.get_safe_value_in_yuan(YEAR, name, stmt)
            print(f'    {name}: {v:,.2f}')

        # 3. 调用公式计算
        formula_fn = FORMULA_MAP[rid]
        actual = formula_fn(project, YEAR)
        print(f'  [公式结果] actual_value = {actual}')

        # 4. 判定 status
        if actual is None:
            status = RuleStatus.NOT_APPLICABLE
            print(f'  [判定] actual is None -> NOT_APPLICABLE (数据缺失)')
        else:
            status = _classify_status(actual, {}, rid)
            print(f'  [判定] {actual:.4f} -> {status.value}')

        # 5. 给出修复建议
        if actual is not None and status in (RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE):
            # 检查是否因未识别科目导致
            has_unrecognized = False
            for name, stmt in subjects:
                li = project.get_line_item(YEAR, name, stmt)
                if li is None or li.original_value is None:
                    has_unrecognized = True
                    print(f'  ⚠ 可能因 "{name}" 未识别/值为空导致假阳性 {status.value}')
            if not has_unrecognized:
                print(f'  ℹ 科目均已识别且非空，{status.value} 判定真实')


if __name__ == '__main__':
    main()
