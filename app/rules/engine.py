# -*- coding: utf-8 -*-
"""
规则执行引擎。

职责：
1. 对某年执行某条规则 → 产出 RuleResult
2. 对所有年份 × 所有规则批量执行
3. 对未实现的 Phase 3 规则返回 NOT_APPLICABLE，提示用户"将在后续 Phase 实现"
4. 数据缺失返回 NOT_APPLICABLE，提示"数据缺失，无法计算该指标"

实现要点：
- 公式是否已实现由 _FORMULA_MAP 判定（与 rules.json 的 implemented_phase1 字段语义一致）
- 阈值判定集中在 _classify_status
- conclusion 文字按 rule.conclusion_template 渲染，{status} 部分会扩展为更详细的程度说明
"""
from typing import List

from app.calculation import formulas
from app.config import format_yuan
from app.models.line_item import LineItem
from app.models.project import AnalysisProject
from app.models.rule import Rule, RuleResult, RuleStatus
from app.rules.thresholds import load_rules


# 公式名 → formulas 模块函数映射（全部 22 条规则）
_FORMULA_MAP = {
    "asset_liability_ratio": formulas.asset_liability_ratio,
    "quasi_cash_minus_interest_bearing": formulas.quasi_cash_minus_interest_bearing,
    "total_assets_growth": formulas.total_assets_growth,
    "payables_minus_receivables": formulas.payables_minus_receivables,
    "receivable_contract_asset_ratio": formulas.receivable_contract_asset_ratio,
    "fixed_assets_ratio": formulas.fixed_assets_ratio,
    "investment_assets_ratio": formulas.investment_assets_ratio,
    "inventory_goodwill_risk": formulas.inventory_goodwill_risk,
    "revenue_growth": formulas.revenue_growth,
    "gross_margin": formulas.gross_margin,
    "expense_ratio_to_gross_margin": formulas.expense_ratio_to_gross_margin,
    "selling_expense_ratio": formulas.selling_expense_ratio,
    "main_profit_ratio": formulas.main_profit_ratio,
    "net_profit_cash_ratio_5y_avg": formulas.net_profit_cash_ratio_5y_avg,
    "roe": formulas.roe,
    "capex_to_operating_cashflow": formulas.capex_to_operating_cashflow,
    "dividend_to_operating_cashflow": formulas.dividend_to_operating_cashflow,
    "cash_interest_yield": formulas.cash_interest_yield,
    "prepayment_ratio": formulas.prepayment_ratio,
    "prepay_plus_other_receivable_ratio": formulas.prepay_plus_other_receivable_ratio,
    "cash_receipt_ratio": formulas.cash_receipt_ratio,
    "net_profit_cash_ratio": formulas.net_profit_cash_ratio,
    # 课程 12 个真实性信号中补齐的 3 个 BS-based 公式（2026-09-16）
    "cash_interest_debt_combo": formulas.cash_interest_debt_combo,  # 高货币+高有息负债组合
    "fixed_assets_growth_yoy": formulas.fixed_assets_growth_yoy,    # 固定+在建 yoy
    "gross_margin_volatility": formulas.gross_margin_volatility,      # 毛利率波动幅度
}


# 各规则计算时实际引用的科目（用于收集 evidence；跨表科目标注报表类型）
_EVIDENCE_SUBJECTS = {
    "asset_liability_ratio": [("总负债", "合并资产负债表"), ("总资产", "合并资产负债表")],
    "quasi_cash_minus_interest_bearing": [
        ("货币资金", "合并资产负债表"),
        ("交易性金融资产", "合并资产负债表"),
        ("短期借款", "合并资产负债表"),
        ("一年内到期的非流动负债", "合并资产负债表"),
        ("长期借款", "合并资产负债表"),
        ("应付债券", "合并资产负债表"),
        ("长期应付款", "合并资产负债表"),
    ],
    "total_assets_growth": [("总资产", "合并资产负债表")],
    "payables_minus_receivables": [
        ("应付账款", "合并资产负债表"),
        ("预收款项", "合并资产负债表"),
        ("应收账款", "合并资产负债表"),
        ("预付款项", "合并资产负债表"),
    ],
    "receivable_contract_asset_ratio": [
        ("应收账款", "合并资产负债表"),
        ("合同资产", "合并资产负债表"),
        ("总资产", "合并资产负债表"),
    ],
    "fixed_assets_ratio": [
        ("固定资产", "合并资产负债表"),
        ("在建工程", "合并资产负债表"),
        ("总资产", "合并资产负债表"),
    ],
    "investment_assets_ratio": [("总资产", "合并资产负债表")],
    "inventory_goodwill_risk": [
        ("存货", "合并资产负债表"),
        ("商誉", "合并资产负债表"),
        ("应收账款", "合并资产负债表"),
        ("总资产", "合并资产负债表"),
    ],
    "revenue_growth": [("营业收入", "合并利润表")],
    "gross_margin": [
        ("营业收入", "合并利润表"),
        ("营业成本", "合并利润表"),
    ],
    "expense_ratio_to_gross_margin": [
        ("营业收入", "合并利润表"),
        ("销售费用", "合并利润表"),
        ("管理费用", "合并利润表"),
        ("研发费用", "合并利润表"),
        ("财务费用", "合并利润表"),
    ],
    "selling_expense_ratio": [
        ("营业收入", "合并利润表"),
        ("销售费用", "合并利润表"),
    ],
    "main_profit_ratio": [
        ("营业收入", "合并利润表"),
        ("营业成本", "合并利润表"),
        ("税金及附加", "合并利润表"),
        ("销售费用", "合并利润表"),
        ("管理费用", "合并利润表"),
        ("研发费用", "合并利润表"),
        ("财务费用", "合并利润表"),
    ],
    "net_profit_cash_ratio_5y_avg": [
        ("净利润", "合并利润表"),
        ("经营活动产生的现金流量净额", "合并现金流量表"),
    ],
    "roe": [
        ("归属于母公司股东的净利润", "合并利润表"),
        ("归属于母公司所有者权益", "合并资产负债表"),
    ],
    "capex_to_operating_cashflow": [
        ("购建固定资产无形资产和其他长期资产支付的现金", "合并现金流量表"),
        ("经营活动产生的现金流量净额", "合并现金流量表"),
    ],
    "dividend_to_operating_cashflow": [
        ("分配股利利润或偿付利息支付的现金", "合并现金流量表"),
        ("经营活动产生的现金流量净额", "合并现金流量表"),
    ],
    "cash_interest_yield": [
        ("利息收入", "合并利润表"),
        ("货币资金", "合并资产负债表"),
    ],
    "prepayment_ratio": [
        ("预付款项", "合并资产负债表"),
        ("总资产", "合并资产负债表"),
    ],
    "prepay_plus_other_receivable_ratio": [
        ("预付款项", "合并资产负债表"),
        ("其他应收款", "合并资产负债表"),
        ("总资产", "合并资产负债表"),
    ],
    "cash_receipt_ratio": [
        ("销售商品提供劳务收到的现金", "合并现金流量表"),
        ("营业收入", "合并利润表"),
    ],
    "net_profit_cash_ratio": [
        ("经营活动产生的现金流量净额", "合并现金流量表"),
        ("净利润", "合并利润表"),
    ],
    "cash_interest_debt_combo": [
        ("货币资金", "合并资产负债表"),
        ("交易性金融资产", "合并资产负债表"),
        ("短期借款", "合并资产负债表"),
        ("一年内到期的非流动负债", "合并资产负债表"),
        ("长期借款", "合并资产负债表"),
        ("应付债券", "合并资产负债表"),
        ("长期应付款", "合并资产负债表"),
        ("利息费用", "合并利润表"),
    ],
    "fixed_assets_growth_yoy": [
        ("固定资产", "合并资产负债表"),
        ("在建工程", "合并资产负债表"),
    ],
    "gross_margin_volatility": [
        ("营业收入", "合并利润表"),
        ("营业成本", "合并利润表"),
    ],
}


def apply_rule(rule: Rule, project: AnalysisProject, year: int) -> RuleResult:
    """
    对某年执行某条规则。
    - 调用 _FORMULA_MAP 中的公式函数，得到 actual_value
    - actual_value 为 None：NOT_APPLICABLE，"数据缺失"
    - 否则：根据 rule.thresholds 判定 status
    - inventory_goodwill_risk 返回 dict，单独处理
    """
    reference_value = rule.description or ""
    evidence = _collect_evidence(rule, project, year)

    if rule.formula_ref not in _FORMULA_MAP:
        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            year=year,
            actual_value=None,
            reference_value=reference_value,
            status=RuleStatus.NOT_APPLICABLE,
            conclusion="该规则未实现",
            evidence=evidence,
            course_source=rule.course_source,
            is_calculable=False,
        )

    formula_fn = _FORMULA_MAP[rule.formula_ref]
    actual_value = formula_fn(project, year)

    if actual_value is None:
        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            year=year,
            actual_value=None,
            reference_value=reference_value,
            status=RuleStatus.NOT_APPLICABLE,
            conclusion="数据缺失，无法计算该指标",
            evidence=evidence,
            course_source=rule.course_source,
            is_calculable=False,
        )

    # inventory_goodwill_risk 返回 dict，单独处理
    if isinstance(actual_value, dict):
        conclusion = _render_inventory_goodwill_conclusion(actual_value, rule)
        status = _classify_inventory_goodwill_status(actual_value, rule.thresholds)
        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            year=year,
            actual_value=actual_value.get("goodwill_ratio", 0.0),
            reference_value=reference_value,
            status=status,
            conclusion=conclusion,
            evidence=evidence,
            course_source=rule.course_source,
            is_calculable=True,
        )

    status = _classify_status(actual_value, rule.thresholds, rule.id)
    conclusion = _render_conclusion(rule, actual_value, status)

    return RuleResult(
        rule_id=rule.id,
        rule_name=rule.name,
        year=year,
        actual_value=actual_value,
        reference_value=reference_value,
        status=status,
        conclusion=conclusion,
        evidence=evidence,
        course_source=rule.course_source,
        is_calculable=True,
    )


def _classify_status(value: float, thresholds: dict, rule_id: str) -> RuleStatus:
    """根据阈值判定 status（处理所有 22 条规则）"""
    # 资产负债率：≥60% 淘汰；40%-60% 关注；<40% 优势
    if rule_id == "asset_liability_ratio":
        if value >= 0.60:
            return RuleStatus.ELIMINATE
        if value >= 0.40:
            return RuleStatus.ATTENTION
        return RuleStatus.ADVANTAGE

    # 准货币-有息负债：<0 淘汰；≥0 优势
    if rule_id == "quasi_cash_minus_interest_bearing":
        if value < 0:
            return RuleStatus.ELIMINATE
        return RuleStatus.ADVANTAGE

    # 总资产增长率：>10% 优势；0-10% 关注；<0 高风险
    if rule_id == "total_assets_growth":
        if value >= 0.10:
            return RuleStatus.ADVANTAGE
        if value >= 0:
            return RuleStatus.ATTENTION
        return RuleStatus.HIGH_RISK

    # 应付预收-应收预付：<0 淘汰；≥0 优势
    if rule_id == "payables_minus_receivables":
        if value < 0:
            return RuleStatus.ELIMINATE
        return RuleStatus.ADVANTAGE

    # (应收账款+合同资产)/总资产：<3% 优势；3-15% 关注；≥15% 淘汰
    if rule_id == "receivable_contract_asset_ratio":
        if value >= 0.15:
            return RuleStatus.ELIMINATE
        if value >= 0.03:
            return RuleStatus.ATTENTION
        if value >= 0.10:
            return RuleStatus.HIGH_RISK
        return RuleStatus.ADVANTAGE

    # (固定资产+在建工程)/总资产：<20% 优势；20-40% 关注；≥40% 淘汰
    if rule_id == "fixed_assets_ratio":
        if value >= 0.40:
            return RuleStatus.ELIMINATE
        if value >= 0.20:
            return RuleStatus.ATTENTION
        return RuleStatus.ADVANTAGE

    # 投资类资产/总资产：≥10% 淘汰；<10% 优势
    if rule_id == "investment_assets_ratio":
        if value >= 0.10:
            return RuleStatus.ELIMINATE
        return RuleStatus.ADVANTAGE

    # 营业收入增长率：≥10% 优势；0-10% 淘汰（<10% 即淘汰）；<0 高风险
    if rule_id == "revenue_growth":
        if value >= 0.10:
            return RuleStatus.ADVANTAGE
        if value >= 0:
            return RuleStatus.ELIMINATE  # 课程：<10% 淘汰
        return RuleStatus.HIGH_RISK

    # 毛利率：≥40% 优势；<40% 淘汰
    if rule_id == "gross_margin":
        if value >= 0.40:
            return RuleStatus.ADVANTAGE
        return RuleStatus.ELIMINATE

    # 期间费用率/毛利率：<40% 优势；≥60% 淘汰；40-60% 关注
    if rule_id == "expense_ratio_to_gross_margin":
        if value >= 0.60:
            return RuleStatus.ELIMINATE
        if value >= 0.40:
            return RuleStatus.ATTENTION
        return RuleStatus.ADVANTAGE

    # 销售费用率：<15% 优势；15-30% 关注；≥30% 淘汰
    if rule_id == "selling_expense_ratio":
        if value >= 0.30:
            return RuleStatus.ELIMINATE
        if value >= 0.15:
            return RuleStatus.ATTENTION
        return RuleStatus.ADVANTAGE

    # 主营利润率：≥15% 优势；<15% 淘汰
    if rule_id == "main_profit_ratio":
        if value >= 0.15:
            return RuleStatus.ADVANTAGE
        return RuleStatus.ELIMINATE

    # 5年平均净现比：≥1.20 优势；≥1.00 正常；<1.00 淘汰；<0.80 高风险
    if rule_id == "net_profit_cash_ratio_5y_avg":
        if value >= 1.20:
            return RuleStatus.ADVANTAGE
        if value >= 1.00:
            return RuleStatus.NORMAL
        if value < 0.80:
            return RuleStatus.HIGH_RISK
        return RuleStatus.ELIMINATE

    # ROE：≥20% 优势；≥15% 正常；<15% 淘汰
    if rule_id == "roe":
        if value >= 0.20:
            return RuleStatus.ADVANTAGE
        if value >= 0.15:
            return RuleStatus.NORMAL
        return RuleStatus.ELIMINATE

    # 资本开支/经营现金流：3%-100% 优势（合理区间）；<3% 或 >100% 淘汰
    if rule_id == "capex_to_operating_cashflow":
        if value < 0.03 or value > 1.00:
            return RuleStatus.ELIMINATE
        return RuleStatus.ADVANTAGE

    # 分红/经营现金流：20%-70% 优势；<20% 或 >70% 关注
    if rule_id == "dividend_to_operating_cashflow":
        if value < 0.20 or value > 0.70:
            return RuleStatus.ATTENTION
        return RuleStatus.ADVANTAGE

    # 现金利息收益率（真实性检测）：≥2.5% 优势；<2% 关注；中间正常
    if rule_id == "auth_cash_interest_yield":
        if value >= 0.025:
            return RuleStatus.ADVANTAGE
        if value < 0.02:
            return RuleStatus.ATTENTION
        return RuleStatus.NORMAL

    # 预付款项/总资产（真实性检测）：<1% 优势；>3% 关注；其他正常
    if rule_id == "auth_prepayment_ratio":
        if value < 0.01:
            return RuleStatus.ADVANTAGE
        if value > 0.03:
            return RuleStatus.ATTENTION
        return RuleStatus.NORMAL

    # (预付+其他应收)/总资产（真实性检测）：>10% 高风险；其他正常
    if rule_id == "auth_prepay_other_receivable":
        if value > 0.10:
            return RuleStatus.HIGH_RISK
        return RuleStatus.NORMAL

    # 收现比（真实性检测）：≥1.20 优势；≥1.10 优势；≥1.00 正常；<0.80 高风险；其他关注
    if rule_id == "auth_cash_receipt_ratio":
        if value >= 1.20:
            return RuleStatus.ADVANTAGE
        if value >= 1.10:
            return RuleStatus.ADVANTAGE
        if value >= 1.00:
            return RuleStatus.NORMAL
        if value < 0.80:
            return RuleStatus.HIGH_RISK
        return RuleStatus.ATTENTION

    # 净现比（真实性检测）：≥1.20 优势；≥1.00 正常；<0.80 高风险；0.80-1.00 关注
    if rule_id == "auth_net_profit_cash_ratio":
        if value >= 1.20:
            return RuleStatus.ADVANTAGE
        if value >= 1.00:
            return RuleStatus.NORMAL
        if value < 0.80:
            return RuleStatus.HIGH_RISK
        return RuleStatus.ATTENTION

    # 高货币+高有息负债+高利息组合（真实性检测）：息差倍数 = (有息负债-准货币资金)/利息费用
    if rule_id == "auth_cash_interest_debt_combo":
        if value <= 0:
            return RuleStatus.ADVANTAGE  # 货币资金≥有息负债，无息差压力
        if value > 5:
            return RuleStatus.HIGH_RISK  # 典型康美药业特征
        return RuleStatus.ATTENTION

    # (固定+在建) yoy：>50% 高风险；>30% 关注；负值/小正值 优势
    if rule_id == "auth_fixed_assets_growth":
        if value > 0.50:
            return RuleStatus.HIGH_RISK
        if value > 0.30:
            return RuleStatus.ATTENTION
        return RuleStatus.ADVANTAGE

    # 毛利率波动幅度：>20% 关注（毛利率突变的常见造假信号）
    if rule_id == "auth_gross_margin_volatility":
        if value > 0.20:
            return RuleStatus.ATTENTION
        return RuleStatus.NORMAL

    return RuleStatus.NOT_APPLICABLE


def _classify_inventory_goodwill_status(value: dict, thresholds: dict) -> RuleStatus:
    """存货商誉爆雷风险状态判定"""
    receivable_ratio = value.get("receivable_ratio", 0)
    inventory_ratio = value.get("inventory_ratio", 0)
    goodwill_ratio = value.get("goodwill_ratio", 0)
    # 商誉/总资产 >10% 淘汰；>5% 关注；存货/总资产 >15% 且应收 >5% 淘汰
    if goodwill_ratio > 0.10:
        return RuleStatus.ELIMINATE
    if goodwill_ratio > 0.05:
        return RuleStatus.ATTENTION
    if receivable_ratio > 0.05 and inventory_ratio > 0.15:
        return RuleStatus.ELIMINATE
    if inventory_ratio > 0.15:
        return RuleStatus.ATTENTION
    return RuleStatus.ADVANTAGE


def _render_inventory_goodwill_conclusion(value: dict, rule: Rule) -> str:
    """存货商誉风险结论"""
    inv_ratio = value.get("inventory_ratio", 0)
    gw_ratio = value.get("goodwill_ratio", 0)
    rec_ratio = value.get("receivable_ratio", 0)
    return (
        f"存货/总资产={inv_ratio:.2%}，商誉/总资产={gw_ratio:.2%}，"
        f"应收账款/总资产={rec_ratio:.2%}"
    )


def apply_all(project: AnalysisProject, rules_path: str = None) -> List[RuleResult]:
    """
    对所有年份、所有规则执行。
    - 只对 implemented_phase1=true 的规则执行（其他规则也产出 NOT_APPLICABLE 结果，提示用户"将在后续 Phase 实现"）
    - 实际 Phase 1：遍历 project.get_years() × 已实现的规则
    - 把结果设置到 project.rule_results
    - 返回结果列表
    """
    rules, _ = load_rules(rules_path)
    results: List[RuleResult] = []
    for year in project.get_years():
        for rule in rules:
            results.append(apply_rule(rule, project, year))
    project.rule_results = results
    return results


# === 内部辅助 ===


def _collect_evidence(
    rule: Rule, project: AnalysisProject, year: int
) -> List[LineItem]:
    """收集 actual_value 计算用到的 LineItem 列表（按 _EVIDENCE_SUBJECTS 中(科目,报表)元组）"""
    subjects = _EVIDENCE_SUBJECTS.get(rule.id, [])
    if not subjects:
        return []
    evidence: List[LineItem] = []
    for entry in subjects:
        # 支持 (name, statement_type) 元组或纯字符串
        if isinstance(entry, tuple):
            name, stmt = entry
        else:
            name, stmt = entry, rule.statement_type or None
        li = project.get_line_item(year, name, stmt)
        if li is not None:
            evidence.append(li)
    return evidence


def _render_conclusion(
    rule: Rule, value: float, status: RuleStatus
) -> str:
    """
    按 rule.conclusion_template 渲染 conclusion 文字。
    - {value:.2%}：按百分比格式（用于比率类规则）
    - {value}：按元格式（format_yuan，用于金额类规则）
    - {status}：扩展为更详细的程度说明
    """
    template = rule.conclusion_template or ""
    status_text = _status_detail_text(rule.id, status, value)

    # 先替换 {status}（避免 status 文本中包含 {value} 等占位符造成误解析）
    template = template.replace("{status}", status_text)

    # 再处理 {value}
    if "{value:.2%}" in template:
        # 比率类：用 Python 的 % 格式
        template = template.replace("{value:.2%}", f"{value:.2%}")
    elif "{value}" in template:
        # 金额类：用 format_yuan（亿/万/元）
        template = template.replace("{value}", format_yuan(value))

    return template


def _status_detail_text(
    rule_id: str, status: RuleStatus, value: float
) -> str:
    """
    把 RuleStatus 枚举值扩展为更详细的程度说明文字，
    让 conclusion 更清晰（如"低于 40% 参考线，基本无风险"）。
    """
    if rule_id == "asset_liability_ratio":
        if status == RuleStatus.ADVANTAGE:
            return "低于 40% 参考线，基本无风险"
        if status == RuleStatus.ATTENTION:
            return "处于 40%-60% 区间，风险较小但存在"
        if status == RuleStatus.ELIMINATE:
            if value > 0.70:
                return "超过 70% 警戒线，偿债风险较大"
            return "超过 60% 淘汰线，存在偿债风险"
    elif rule_id == "quasi_cash_minus_interest_bearing":
        if status == RuleStatus.ADVANTAGE:
            return "差额 ≥ 0，无偿债风险"
        if status == RuleStatus.ELIMINATE:
            return "差额 < 0，偿债风险较高"
    return status.value
