# -*- coding: utf-8 -*-
"""模拟修改后的 _build_summary 输出格式"""
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
    ('auth_cash_interest_yield', '现金利息收益率', formulas.cash_interest_yield),
    ('auth_prepayment_ratio', '预付款项/总资产', formulas.prepayment_ratio),
    ('auth_prepay_other_receivable', '(预付+其他应收)/总资产', formulas.prepay_plus_other_receivable_ratio),
    ('auth_cash_receipt_ratio', '收现比', formulas.cash_receipt_ratio),
    ('auth_net_profit_cash_ratio', '净现比', formulas.net_profit_cash_ratio),
]

_STATUS_TEXT = {
    RuleStatus.ADVANTAGE: "正常",
    RuleStatus.NORMAL: "正常",
    RuleStatus.ATTENTION: "关注",
    RuleStatus.HIGH_RISK: "高风险",
    RuleStatus.ELIMINATE: "淘汰",
    RuleStatus.NOT_APPLICABLE: "—",
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


def preview_summary(name, path, year):
    project = build_project(name, path, year)

    results = []
    for rid, rname, formula_fn in AUTH_RULES:
        actual = formula_fn(project, year)
        if actual is None:
            status = RuleStatus.NOT_APPLICABLE
        else:
            status = _classify_status(actual, {}, rid)
        results.append((rid, rname, actual, status))

    status_count = Counter(r[3] for r in results)
    high_risk_count = status_count.get(RuleStatus.HIGH_RISK, 0)
    eliminate_count = status_count.get(RuleStatus.ELIMINATE, 0)
    attention_count = status_count.get(RuleStatus.ATTENTION, 0)

    if eliminate_count > 0 or high_risk_count >= 2:
        risk_level = "🔴 高风险"
        advice = "出现淘汰项或多处高风险，财务数据真实性存疑，强烈不建议投资。"
    elif high_risk_count == 1 or attention_count >= 2:
        risk_level = "🟡 中风险"
        advice = "存在个别异常项，建议进一步结合附注与审计意见核实。"
    elif attention_count == 1:
        risk_level = "🟡 低风险"
        advice = "存在 1 项关注项，整体真实性尚可，留意趋势变化。"
    else:
        risk_level = "🟢 低风险"
        advice = "5 项真实性指标均正常，财务数据真实性较好。"

    # 收集存疑项
    suspicious_items = []
    for rid, rname, actual, status in results:
        if status in (RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE, RuleStatus.ATTENTION):
            val_str = f"{actual:.2%}" if actual is not None else "—"
            suspicious_items.append(f"  • {rname}：{val_str}（{_STATUS_TEXT[status]}）")

    parts = []
    for st in [RuleStatus.ADVANTAGE, RuleStatus.NORMAL, RuleStatus.ATTENTION,
               RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE, RuleStatus.NOT_APPLICABLE]:
        n = status_count.get(st, 0)
        if n > 0:
            parts.append(f"{_STATUS_TEXT[st]} {n} 项")
    summary = "　|　".join(parts)

    suspicious_text = ""
    if suspicious_items:
        suspicious_text = "\n\n真实性存疑项（按严重程度）：\n" + "\n".join(suspicious_items)

    print(f'\n{"="*60}')
    print(f'【{name}】 {year} 年报 - {risk_level}')
    print("="*60)
    print(f'全部 {len(results)} 项检测结果：{summary}')
    print(f'综合建议：{advice}{suspicious_text}')


for name, path, year in TEST_CASES:
    preview_summary(name, path, year)
