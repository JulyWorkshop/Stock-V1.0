# -*- coding: utf-8 -*-
"""
财务计算公式层 - 完整实现 22 条规则所需的全部公式。

约定：
- 金额类公式输入与输出统一为"元"
- 比率类公式输出为小数（如 0.6 表示 60%）
- 未识别科目按 0 计算（用 safe_value_in_yuan）；分母为 0 返回 None
- 课程出处严格依据 12 周课程 PDF 原文
"""
import json
from typing import Optional, Dict, List

from app.config import RULES_FILE
from app.models.project import AnalysisProject


# 模块级缓存：subject_groups（rules.json 中的科目组定义）
_SUBJECT_GROUPS_CACHE: Optional[dict] = None


def _get_subject_groups() -> dict:
    """加载 rules.json 中的 subject_groups 字段（带缓存）"""
    global _SUBJECT_GROUPS_CACHE
    if _SUBJECT_GROUPS_CACHE is None:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _SUBJECT_GROUPS_CACHE = data.get("subject_groups", {}) or {}
    return _SUBJECT_GROUPS_CACHE


# ============================================================
# 资产负债表类公式（step 3-9）
# ============================================================


def asset_liability_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """资产负债率 = 总负债 / 总资产；课程第15周第5页/第19周第3页"""
    total_liabilities = project.get_safe_value_in_yuan(year, "总负债", "合并资产负债表")
    total_assets = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    if total_assets == 0:
        return None
    return total_liabilities / total_assets


def quasi_cash_minus_interest_bearing(project: AnalysisProject, year: int) -> Optional[float]:
    """准货币资金 - 有息负债 = (货币资金+交易性金融资产)-(短期借款+一年内到期+长期借款+应付债券+长期应付款)"""
    quasi_cash = sum_subject_group(project, year, "quasi_cash", "合并资产负债表")
    interest_bearing = sum_subject_group(project, year, "interest_bearing_liabilities", "合并资产负债表")
    if quasi_cash is None or interest_bearing is None:
        return None
    return quasi_cash - interest_bearing


def total_assets_growth(project: AnalysisProject, year: int) -> Optional[float]:
    """总资产同比增长率 = (本年总资产 - 上年总资产) / 上年总资产；课程第19周第2页"""
    years = project.get_years()
    if year not in years:
        return None
    idx = years.index(year)
    if idx == 0:
        return None  # 第一年无上年数据
    prev_year = years[idx - 1]
    curr = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    prev = project.get_safe_value_in_yuan(prev_year, "总资产", "合并资产负债表")
    if prev == 0:
        return None
    return (curr - prev) / prev


def payables_minus_receivables(project: AnalysisProject, year: int) -> Optional[float]:
    """应付预收 - 应收预付 = (应付票据+应付账款+预收款项+合同负债)-(应收票据+应收账款+应收款项融资+预付款项+合同资产)"""
    payables = sum_subject_group(project, year, "payables_and_advances", "合并资产负债表")
    receivables = sum_subject_group(project, year, "receivables_and_prepayments", "合并资产负债表")
    if payables is None or receivables is None:
        return None
    return payables - receivables


def receivable_contract_asset_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """(应收账款+合同资产)/总资产；课程第15周第11页"""
    receivable = project.get_safe_value_in_yuan(year, "应收账款", "合并资产负债表")
    contract_asset = project.get_safe_value_in_yuan(year, "合同资产", "合并资产负债表")
    total_assets = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    if total_assets == 0:
        return None
    return (receivable + contract_asset) / total_assets


def fixed_assets_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """(固定资产+在建工程)/总资产；课程第15周第12页"""
    fixed = sum_subject_group(project, year, "fixed_assets_construction", "合并资产负债表")
    total_assets = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    if fixed is None or total_assets == 0:
        return None
    return fixed / total_assets


def cash_interest_debt_combo(project: AnalysisProject, year: int) -> Optional[float]:
    """高货币资金+高有息负债+高额利息支出 组合检测（课程第16周第6-7页）
    返回 (有息负债 - 货币资金) / 利息费用 = 缺口倍数。
    - 缺口倍数 <= 0（货币资金 ≥ 有息负债）：正常，无息差压力
    - 缺口倍数 > 0 但 <= 5：关注，存在息差但不大
    - 缺口倍数 > 5：高风险，康美药业典型特征（账上1000亿货币，但有息负债+利息费用远超）
    课程阈值（参考）：当 (货币资金+交易性金融资产) ≥ 有息负债 AND 利息费用/(货币资金+有息负债) > 5%
    时进一步标红。
    """
    quasi_cash = sum_subject_group(project, year, "quasi_cash", "合并资产负债表")  # 货币资金+交易性金融资产
    interest_bearing = sum_subject_group(project, year, "interest_bearing_liabilities", "合并资产负债表")
    interest_expense = project.get_safe_value_in_yuan(year, "利息费用", "合并利润表")
    if not quasi_cash or not interest_bearing:
        return None
    if interest_expense == 0:
        return None
    gap = interest_bearing - quasi_cash
    return gap / interest_expense


def fixed_assets_growth_yoy(project: AnalysisProject, year: int) -> Optional[float]:
    """(固定资产+在建工程) 同比增长率（课程第15周第12页）
    返回 current/prior - 1。需多年数据；只有 1 年时返回 None。
    """
    years = project.get_years()
    if year not in years or len(years) < 2:
        return None
    idx = years.index(year)
    if idx == 0:
        return None
    prior_year = years[idx - 1]
    cur = sum_subject_group(project, year, "fixed_assets_construction", "合并资产负债表")
    pri = sum_subject_group(project, prior_year, "fixed_assets_construction", "合并资产负债表")
    if not cur or not pri or pri == 0:
        return None
    return cur / pri - 1


def gross_margin_volatility(project: AnalysisProject, year: int) -> Optional[float]:
    """毛利率同比波动幅度（课程第17周第35-36页）
    返回 abs(current - prior)。>20% 异常。
    """
    years = project.get_years()
    if year not in years or len(years) < 2:
        return None
    idx = years.index(year)
    if idx == 0:
        return None
    prior_year = years[idx - 1]
    cur = gross_margin(project, year)
    pri = gross_margin(project, prior_year)
    if cur is None or pri is None:
        return None
    return abs(cur - pri)


def investment_assets_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """投资类资产/总资产；课程第15周第14页"""
    inv = sum_subject_group(project, year, "investment_assets", "合并资产负债表")
    total_assets = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    if inv is None or total_assets == 0:
        return None
    return inv / total_assets


def inventory_goodwill_risk(project: AnalysisProject, year: int) -> Optional[Dict]:
    """存货商誉爆雷风险检查 - 返回 dict 含多项指标；课程第15周第15-16页"""
    total_assets = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    if total_assets == 0:
        return None
    inventory = project.get_safe_value_in_yuan(year, "存货", "合并资产负债表")
    goodwill = project.get_safe_value_in_yuan(year, "商誉", "合并资产负债表")
    receivable = project.get_safe_value_in_yuan(year, "应收账款", "合并资产负债表")
    return {
        "inventory_ratio": inventory / total_assets,
        "goodwill_ratio": goodwill / total_assets,
        "receivable_ratio": receivable / total_assets,
        "total_assets": total_assets,
    }


# ============================================================
# 利润表类公式（step 10-14）
# ============================================================


def revenue_growth(project: AnalysisProject, year: int) -> Optional[float]:
    """营业收入同比增长率；课程第17周第13页"""
    years = project.get_years()
    if year not in years:
        return None
    idx = years.index(year)
    if idx == 0:
        return None
    prev_year = years[idx - 1]
    curr = project.get_safe_value_in_yuan(year, "营业收入", "合并利润表")
    prev = project.get_safe_value_in_yuan(prev_year, "营业收入", "合并利润表")
    if prev == 0:
        return None
    return (curr - prev) / prev


def gross_margin(project: AnalysisProject, year: int) -> Optional[float]:
    """毛利率 = (营业收入-营业成本)/营业收入；课程第17周第35-36页"""
    revenue = project.get_safe_value_in_yuan(year, "营业收入", "合并利润表")
    cost = project.get_safe_value_in_yuan(year, "营业成本", "合并利润表")
    if revenue == 0:
        return None
    return (revenue - cost) / revenue


def expense_ratio_to_gross_margin(project: AnalysisProject, year: int) -> Optional[float]:
    """期间费用率/毛利率；课程第17周第23页
    期间费用 = 销售费用 + 管理费用 + 研发费用 + 财务费用
    """
    revenue = project.get_safe_value_in_yuan(year, "营业收入", "合并利润表")
    if revenue == 0:
        return None
    selling = project.get_safe_value_in_yuan(year, "销售费用", "合并利润表")
    admin = project.get_safe_value_in_yuan(year, "管理费用", "合并利润表")
    rd = project.get_safe_value_in_yuan(year, "研发费用", "合并利润表")
    finance = project.get_safe_value_in_yuan(year, "财务费用", "合并利润表")
    period_expense = selling + admin + rd + finance
    period_expense_ratio = period_expense / revenue
    gross = gross_margin(project, year)
    if gross is None or gross == 0:
        return None
    return period_expense_ratio / gross


def selling_expense_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """销售费用率 = 销售费用/营业收入；课程第17周第27页"""
    revenue = project.get_safe_value_in_yuan(year, "营业收入", "合并利润表")
    if revenue == 0:
        return None
    selling = project.get_safe_value_in_yuan(year, "销售费用", "合并利润表")
    return selling / revenue


def main_profit_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """主营利润率 = 主营利润/营业收入
    主营利润 = 营业收入 - 营业成本 - 税金及附加 - 销售费用 - 管理费用 - 研发费用 - 财务费用
    课程第17周第28-30页
    """
    revenue = project.get_safe_value_in_yuan(year, "营业收入", "合并利润表")
    if revenue == 0:
        return None
    cost = project.get_safe_value_in_yuan(year, "营业成本", "合并利润表")
    tax = project.get_safe_value_in_yuan(year, "税金及附加", "合并利润表")
    selling = project.get_safe_value_in_yuan(year, "销售费用", "合并利润表")
    admin = project.get_safe_value_in_yuan(year, "管理费用", "合并利润表")
    rd = project.get_safe_value_in_yuan(year, "研发费用", "合并利润表")
    finance = project.get_safe_value_in_yuan(year, "财务费用", "合并利润表")
    main_profit = revenue - cost - tax - selling - admin - rd - finance
    return main_profit / revenue


# ============================================================
# 跨表类公式（step 15-16）
# ============================================================


def net_profit_cash_ratio_5y_avg(project: AnalysisProject, year: int) -> Optional[float]:
    """过去5年平均净现比 = mean(经营现金流净额/净利润) over 最近5年
    课程第18周第7页
    """
    years = project.get_years()
    if year not in years:
        return None
    idx = years.index(year)
    # 取当前年及之前4年（最多5年）
    start_idx = max(0, idx - 4)
    relevant_years = years[start_idx:idx + 1]
    if len(relevant_years) < 1:
        return None
    ratios = []
    for y in relevant_years:
        np = project.get_safe_value_in_yuan(y, "净利润", "合并利润表")
        ocf = project.get_safe_value_in_yuan(y, "经营活动产生的现金流量净额", "合并现金流量表")
        if np == 0:
            continue
        ratios.append(ocf / np)
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


def roe(project: AnalysisProject, year: int) -> Optional[float]:
    """ROE = 归母净利润 / 归母所有者权益；课程第17周第34页"""
    np_parent = project.get_safe_value_in_yuan(year, "归属于母公司股东的净利润", "合并利润表")
    equity_parent = project.get_safe_value_in_yuan(year, "归属于母公司所有者权益", "合并资产负债表")
    if equity_parent == 0:
        return None
    return np_parent / equity_parent


# ============================================================
# 现金流量表类公式（step 17-18）
# ============================================================


def capex_to_operating_cashflow(project: AnalysisProject, year: int) -> Optional[float]:
    """购建长期资产支付现金/经营活动现金流量净额；课程第18周第8页"""
    capex = project.get_safe_value_in_yuan(
        year, "购建固定资产无形资产和其他长期资产支付的现金", "合并现金流量表"
    )
    ocf = project.get_safe_value_in_yuan(
        year, "经营活动产生的现金流量净额", "合并现金流量表"
    )
    if ocf == 0:
        return None
    return abs(capex) / abs(ocf)


def dividend_to_operating_cashflow(project: AnalysisProject, year: int) -> Optional[float]:
    """分红现金/经营现金流；课程第18周第9页"""
    dividend = project.get_safe_value_in_yuan(
        year, "分配股利利润或偿付利息支付的现金", "合并现金流量表"
    )
    ocf = project.get_safe_value_in_yuan(
        year, "经营活动产生的现金流量净额", "合并现金流量表"
    )
    if ocf == 0:
        return None
    return abs(dividend) / abs(ocf)


# ============================================================
# 财务真实性检测（step 19-22）
# ============================================================


def cash_interest_yield(project: AnalysisProject, year: int) -> Optional[float]:
    """现金利息收益率 = 利息收入/货币资金；课程第16周第6-7页"""
    interest_income = project.get_safe_value_in_yuan(year, "利息收入", "合并利润表")
    cash = project.get_safe_value_in_yuan(year, "货币资金", "合并资产负债表")
    if cash == 0:
        return None
    return interest_income / cash


def prepayment_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """预付款项/总资产；课程第14周第30页"""
    prepay = project.get_safe_value_in_yuan(year, "预付款项", "合并资产负债表")
    total = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    if total == 0:
        return None
    return prepay / total


def prepay_plus_other_receivable_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """(预付款项+其他应收款)/总资产；课程第16周第9页"""
    prepay = project.get_safe_value_in_yuan(year, "预付款项", "合并资产负债表")
    other_rec = project.get_safe_value_in_yuan(year, "其他应收款", "合并资产负债表")
    total = project.get_safe_value_in_yuan(year, "总资产", "合并资产负债表")
    if total == 0:
        return None
    return (prepay + other_rec) / total


def cash_receipt_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """收现比 = 销售商品提供劳务收到的现金/营业收入；课程第17周第14页"""
    cash_in = project.get_safe_value_in_yuan(
        year, "销售商品提供劳务收到的现金", "合并现金流量表"
    )
    revenue = project.get_safe_value_in_yuan(year, "营业收入", "合并利润表")
    if revenue == 0:
        return None
    return cash_in / revenue


def net_profit_cash_ratio(project: AnalysisProject, year: int) -> Optional[float]:
    """净现比 = 经营活动现金流量净额/净利润；课程第18周第7页"""
    ocf = project.get_safe_value_in_yuan(
        year, "经营活动产生的现金流量净额", "合并现金流量表"
    )
    np = project.get_safe_value_in_yuan(year, "净利润", "合并利润表")
    if np == 0:
        return None
    return ocf / np


# ============================================================
# 科目组求和辅助
# ============================================================


def sum_subject_group(
    project: AnalysisProject,
    year: int,
    group_name: str,
    statement_type: str = "合并资产负债表",
) -> Optional[float]:
    """按 rules.json 中 subject_groups 求某组科目总和（元）。未识别按 0 计算。"""
    groups = _get_subject_groups()
    group = groups.get(group_name)
    if group is None:
        return None
    items = group.get("items", [])
    if not items:
        return None
    total = 0.0
    for name in items:
        v = project.get_safe_value_in_yuan(year, name, statement_type)
        total += v
    return total
