# -*- coding: utf-8 -*-
"""诊断5家公司真实性检测的综合判定"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

from collections import Counter
from app.pdf.parsers.table_parser import parse_statement_by_table
from app.pdf.page_locator import locate_statement_pages
from app.models.project import AnalysisProject
from app.models.company import Company
from app.calculation import formulas
from app.rules.engine import _classify_status
from app.models.rule import RuleStatus

TEST_CASES = [
    ('ST卓然', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf', 2025),
    ('大唐药业', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf', 2025),
    ('贵州茅台', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf', 2018),
    ('天键股份', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\1ebd8903-d4f6-410e-873a-25e36b1cc605_58c3aff0-bb5d-4f19-96af-8b36d1a8bac0_天键股份：2025年年度报告（更正后）.pdf', 2025),
    ('岩山科技', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\91132a2d-d9f0-4907-bdca-6664b8f56b52_075d5e45-a1da-4258-aa6b-7307074a9136_岩山科技：2025年年度报告（更正后）.pdf', 2025),
]

AUTH_RULES = [
    'auth_cash_interest_yield',
    'auth_prepayment_ratio',
    'auth_prepay_other_receivable',
    'auth_cash_receipt_ratio',
    'auth_net_profit_cash_ratio',
]

RULE_SUBJECTS = {
    'auth_cash_interest_yield': [('利息收入', '合并利润表'), ('货币资金', '合并资产负债表')],
    'auth_prepayment_ratio': [('预付款项', '合并资产负债表'), ('总资产', '合并资产负债表')],
    'auth_prepay_other_receivable': [('预付款项', '合并资产负债表'), ('其他应收款', '合并资产负债表'), ('总资产', '合并资产负债表')],
    'auth_cash_receipt_ratio': [('销售商品提供劳务收到的现金', '合并现金流量表'), ('营业收入', '合并利润表')],
    'auth_net_profit_cash_ratio': [('经营活动产生的现金流量净额', '合并现金流量表'), ('净利润', '合并利润表')],
}

FORMULA_MAP = {
    'auth_cash_interest_yield': formulas.cash_interest_yield,
    'auth_prepayment_ratio': formulas.prepayment_ratio,
    'auth_prepay_other_receivable': formulas.prepay_plus_other_receivable_ratio,
    'auth_cash_receipt_ratio': formulas.cash_receipt_ratio,
    'auth_net_profit_cash_ratio': formulas.net_profit_cash_ratio,
}


def build_project(name, path, year):
    company = Company(name=name, stock_code='')
    project = AnalysisProject(company=company)
    line_items = []
    for stmt in ['合并资产负债表', '合并利润表', '合并现金流量表']:
        items = parse_statement_by_table(path, year, stmt, name)
        line_items.extend(items)
    project.line_items = line_items
    return project


def diagnose(name, path, year):
    print(f'\n{"="*70}')
    print(f'【{name}】 {year} 年报')
    print("="*70)

    project = build_project(name, path, year)

    results = []
    for rid in AUTH_RULES:
        formula_fn = FORMULA_MAP[rid]
        actual = formula_fn(project, year)

        # 检查科目识别
        subjects = RULE_SUBJECTS[rid]
        missing_subjects = []
        for sname, stmt in subjects:
            li = project.get_line_item(year, sname, stmt)
            if li is None or li.original_value is None:
                missing_subjects.append(sname)

        if actual is None:
            status = RuleStatus.NOT_APPLICABLE
        else:
            status = _classify_status(actual, {}, rid)

        results.append((rid, actual, status, missing_subjects))

        val_str = f'{actual:.4f}' if actual is not None else 'None'
        miss_str = f' [缺失:{missing_subjects}]' if missing_subjects else ''
        print(f'  {rid}: value={val_str}, status={status.value}{miss_str}')

    # 综合判定（与 authenticity_page.py _build_summary 一致）
    status_count = Counter(r[2] for r in results)
    high_risk_count = status_count.get(RuleStatus.HIGH_RISK, 0)
    eliminate_count = status_count.get(RuleStatus.ELIMINATE, 0)
    attention_count = status_count.get(RuleStatus.ATTENTION, 0)
    normal_count = status_count.get(RuleStatus.ADVANTAGE, 0) + status_count.get(RuleStatus.NORMAL, 0)
    na_count = status_count.get(RuleStatus.NOT_APPLICABLE, 0)

    if eliminate_count > 0 or high_risk_count >= 2:
        risk_level = "🔴 高风险"
    elif high_risk_count == 1 or attention_count >= 2:
        risk_level = "🟡 中风险"
    elif attention_count == 1:
        risk_level = "🟡 低风险"
    else:
        risk_level = "🟢 低风险"

    print(f'\n  综合判定: {risk_level}')
    print(f'  优势/正常={normal_count}, 关注={attention_count}, '
          f'高风险={high_risk_count}, 淘汰={eliminate_count}, 不适用={na_count}')

    # 列出高风险/淘汰/关注的科目
    suspicious = [(r[0], r[1], r[2]) for r in results
                  if r[2] in (RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE, RuleStatus.ATTENTION)]
    if suspicious:
        print(f'  真实性存疑项:')
        for rid, val, st in suspicious:
            val_str = f'{val:.4f}' if val is not None else 'None'
            print(f'    - {rid}: {val_str} ({st.value})')


for name, path, year in TEST_CASES:
    diagnose(name, path, year)
