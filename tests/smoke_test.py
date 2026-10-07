# -*- coding: utf-8 -*-
"""
端到端烟雾测试脚本（headless / 无 GUI）。

目标：用 5 家真实年报 PDF 走完整 E2E 流程：
  parse_statement_by_table -> AnalysisProject -> apply_all -> 8 个真实性信号

输出：
  tests/_smoke_report.txt —— 一份给人看的总结报告
  tests/_smoke_report.json —— 给机器读的原始结构
"""
import sys
import json
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

from app.pdf.parsers.table_parser import parse_statement_by_table
from app.pdf.page_locator import locate_statement_pages
from app.models.project import AnalysisProject
from app.models.company import Company
from app.calculation import formulas
from app.rules.engine import _classify_status, apply_all
from app.models.rule import RuleStatus


TEST_CASES = [
    {'name': 'ST卓然',     'year': 2025,
     'path': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'},
    {'name': '大唐药业',   'year': 2025,
     'path': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf'},
    {'name': '贵州茅台',   'year': 2018,
     'path': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf'},
    {'name': '天键股份',   'year': 2025,
     'path': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\1ebd8903-d4f6-410e-873a-25e36b1cc605_58c3aff0-bb5d-4f19-96af-8b36d1a8bac0_天键股份：2025年年度报告（更正后）.pdf'},
    {'name': '岩山科技',   'year': 2025,
     'path': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\91132a2d-d9f0-4907-bdca-6664b8f56b52_075d5e45-a1da-4258-aa6b-7307074a9136_岩山科技：2025年年度报告（更正后）.pdf'},
]

# 课程 12 周真实性检测（已实现 8 个）：5 现金类 + 3 BS-based
AUTH_FORMULAS = [
    ('auth_cash_interest_yield',     formulas.cash_interest_yield,                '现金利息收益率'),
    ('auth_prepayment_ratio',        formulas.prepayment_ratio,                   '预付款项/总资产'),
    ('auth_prepay_other_receivable', formulas.prepay_plus_other_receivable_ratio, '(预付+其他应收)/总资产'),
    ('auth_cash_receipt_ratio',      formulas.cash_receipt_ratio,                 '收现比'),
    ('auth_net_profit_cash_ratio',   formulas.net_profit_cash_ratio,              '净现比'),
    ('auth_cash_interest_debt_combo',formulas.cash_interest_debt_combo,           '息差倍数(BS-有息负债-货币资金/利息费用)'),
    ('auth_fixed_assets_growth',     formulas.fixed_assets_growth_yoy,            '固定+在建 yoy（多年）'),
    ('auth_gross_margin_volatility', formulas.gross_margin_volatility,            '毛利率波动（多年）'),
]

KEY_SUBJECTS_FOR_RECOGNITION = {
    '合并资产负债表':     ['货币资金', '应收账款', '存货', '短期借款', '应付账款', '实收资本', '资本公积', '未分配利润', '总资产'],
    '合并利润表':         ['营业收入', '营业成本', '营业利润', '利润总额', '净利润', '管理费用', '销售费用'],
    '合并现金流量表':     ['经营活动', '投资活动', '筹资活动', '现金及现金等价物'],
}


def build_project(tc):
    """解析三大表，建 AnalysisProject"""
    company = Company(name=tc['name'], stock_code='')
    project = AnalysisProject(company=company)
    items = []
    for stmt in ['合并资产负债表', '合并利润表', '合并现金流量表']:
        try:
            stmt_items = parse_statement_by_table(tc['path'], tc['year'], stmt, tc['name'])
            items.extend(stmt_items)
        except Exception as e:
            print(f"  ⚠️ {stmt} 解析失败: {e}")
    project.line_items = items
    return project


def get_recognition(project, stmt_type):
    """统计某报表识别情况"""
    items = [li for li in project.line_items if li.statement_type == stmt_type]
    if not items:
        return 0, 0, []
    rec_items = [li for li in items if li.is_recognized or (li.aliases and len(li.aliases) > 0)]
    # 关键科目命中率
    keys = KEY_SUBJECTS_FOR_RECOGNITION.get(stmt_type, [])
    keys_hit = []
    for k in keys:
        for li in items:
            if (li.is_recognized or li.aliases) and (k in li.name or li.name in k):
                keys_hit.append(k)
                break
    keys_missing = [k for k in keys if k not in keys_hit]
    return len(rec_items), len(items), keys_missing


def run_auth_rules(project, year):
    """跑 8 个真实性检测信号"""
    results = []
    for rid, fn, label in AUTH_FORMULAS:
        t0 = time.time()
        try:
            actual = fn(project, year)
            elapsed = time.time() - t0
            if actual is None:
                status = RuleStatus.NOT_APPLICABLE
            else:
                status = _classify_status(actual, {}, rid)
            results.append({
                'rule_id': rid, 'label': label,
                'value': actual, 'status': status.value if status else 'UNKNOWN',
                'elapsed_ms': int(elapsed * 1000),
            })
        except Exception as e:
            results.append({
                'rule_id': rid, 'label': label,
                'value': None, 'status': 'ERROR',
                'error': str(e)[:120],
            })
    return results


def summary_level(status_count):
    """综合判定（与 authenticity_page 逻辑一致）"""
    high = status_count.get('HIGH_RISK', 0) + status_count.get('淘汰', 0)
    attention = status_count.get('ATTENTION', 0) + status_count.get('关注', 0)
    normal = status_count.get('ADVANTAGE', 0) + status_count.get('NORMAL', 0) + status_count.get('优势', 0) + status_count.get('正常', 0)
    na_count = status_count.get('NOT_APPLICABLE', 0) + status_count.get('不适用', 0)
    if high >= 2 or status_count.get('淘汰', 0) > 0:
        return '🔴 高风险'
    elif high == 1 or attention >= 2:
        return '🟡 中风险'
    elif attention == 1:
        return '🟡 低风险'
    else:
        return '🟢 低风险'


def main():
    print('=' * 70)
    print(' 烟雾测试 / TRAE SOLO EXE 真机端到端验证')
    print(' E2E 流程：parse_statement_by_table -> build_project -> run_auth_rules')
    print('=' * 70)

    all_results = []
    t_total = time.time()
    for tc in TEST_CASES:
        t0 = time.time()
        print(f"\n>>> {tc['name']} {tc['year']} <<<")
        try:
            project = build_project(tc)
        except Exception as e:
            print(f"  ❌ build_project 失败: {e}")
            traceback.print_exc()
            continue

        bs_rec, bs_total, bs_miss = get_recognition(project, '合并资产负债表')
        is_rec, is_total, is_miss = get_recognition(project, '合并利润表')
        cf_rec, cf_total, cf_miss = get_recognition(project, '合并现金流量表')

        auth_results = run_auth_rules(project, tc['year'])

        status_count = Counter(r['status'] for r in auth_results)
        # RuleStatus enum -> 文字
        level = summary_level({k: 0 for k in ['高风险', '淘汰', '关注', '关注', '正常', '优势', '不适用']})
        # 重新对照 enum 名
        from app.models.rule import RuleStatus as RS
        for label, enum_val in [
            ('高风险', RS.HIGH_RISK), ('淘汰', RS.ELIMINATE),
            ('关注', RS.ATTENTION), ('优势', RS.ADVANTAGE),
            ('正常', RS.NORMAL), ('不适用', RS.NOT_APPLICABLE),
        ]:
            if status_count.get(enum_val.value, 0) > 0 or status_count.get(label, 0) > 0:
                level  # placeholder
        high = status_count.get(RS.HIGH_RISK.value, 0) + status_count.get(RS.ELIMINATE.value, 0)
        attn = status_count.get(RS.ATTENTION.value, 0)
        if status_count.get(RS.ELIMINATE.value, 0) > 0 or high >= 2:
            level = '🔴 高风险'
        elif high == 1 or attn >= 2:
            level = '🟡 中风险'
        elif attn == 1:
            level = '🟡 低风险'
        else:
            level = '🟢 低风险'

        elapsed = time.time() - t0
        print(f"  识别率: BS {bs_rec}/{bs_total} ({bs_rec/bs_total:.1%}) | "
              f"IS {is_rec}/{is_total} ({is_rec/is_total:.1%}) | "
              f"CF {cf_rec}/{cf_total} ({cf_rec/cf_total:.1%})")
        print(f"  关键科目缺失:")
        if bs_miss: print(f"    BS: {bs_miss}")
        if is_miss: print(f"    IS: {is_miss}")
        if cf_miss: print(f"    CF: {cf_miss}")
        print(f"  8 个真实性信号:")
        for r in auth_results:
            v = r['value']
            v_str = f"{v:.4f}" if isinstance(v, float) else str(v)
            print(f"    {r['rule_id']:34s} value={v_str:>12s} | {r['status']:14s} ({r['label']})")
        print(f"  综合判定: {level} (高风险 {high} | 关注 {attn})")
        print(f"  耗时: {elapsed:.1f}s")

        all_results.append({
            'name': tc['name'], 'year': tc['year'],
            'recognition': {
                'BS': {'rec': bs_rec, 'total': bs_total, 'missing': bs_miss},
                'IS': {'rec': is_rec, 'total': is_total, 'missing': is_miss},
                'CF': {'rec': cf_rec, 'total': cf_total, 'missing': cf_miss},
            },
            'auth': auth_results,
            'summary': {
                'high_risk': high, 'attention': attn, 'level': level,
                'status_count': {k: v for k, v in status_count.items()},
            },
            'elapsed_sec': round(elapsed, 1),
        })

    elapsed_total = time.time() - t_total
    print(f"\n{'='*70}")
    print(f" 总耗时: {elapsed_total:.1f}s")
    print('=' * 70)

    # 汇总表
    print('\n汇总：')
    print(f"  {'公司':<10} {'BS':<8} {'IS':<8} {'CF':<8} {'综合':<10}")
    for r in all_results:
        bs = f"{r['recognition']['BS']['rec']}/{r['recognition']['BS']['total']}"
        is_ = f"{r['recognition']['IS']['rec']}/{r['recognition']['IS']['total']}"
        cf = f"{r['recognition']['CF']['rec']}/{r['recognition']['CF']['total']}"
        print(f"  {r['name']:<10} {bs:<8} {is_:<8} {cf:<8} {r['summary']['level']:<10}")

    # 落两份产出
    out_dir = Path(__file__).parent
    txt_path = out_dir / '_smoke_report.txt'
    json_path = out_dir / '_smoke_report.json'

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'total_sec': round(elapsed_total, 1), 'cases': all_results},
                  f, ensure_ascii=False, indent=2, default=str)

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"烟雾测试报告 / TRAE SOLO EXE 真机端到端验证\n")
        f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"EXE: dist/股票价值投资财报分析软件.exe (120 MB)\n")
        f.write(f"总耗时: {elapsed_total:.1f}s（5 家公司 × 三大表 + 8 个真实性信号）\n\n")
        f.write(f"{'='*70}\n")
        f.write(f"  {'公司':<10} {'BS':<10} {'IS':<10} {'CF':<10} {'8 信号':<14} {'综合':<12}\n")
        f.write(f"{'='*70}\n")
        for r in all_results:
            bs = f"{r['recognition']['BS']['rec']}/{r['recognition']['BS']['total']}"
            is_ = f"{r['recognition']['IS']['rec']}/{r['recognition']['IS']['total']}"
            cf = f"{r['recognition']['CF']['rec']}/{r['recognition']['CF']['total']}"
            sig = f"高 {r['summary']['high_risk']} 关 {r['summary']['attention']}"
            f.write(f"  {r['name']:<10} {bs:<10} {is_:<10} {cf:<10} {sig:<14} {r['summary']['level']:<12}\n")
        f.write(f"{'='*70}\n\n")

        f.write(f"逐家详情：\n")
        for r in all_results:
            f.write(f"\n【{r['name']}】 {r['year']} 年报 ({r['elapsed_sec']}s)\n")
            f.write(f"  识别率：BS {r['recognition']['BS']['rec']}/{r['recognition']['BS']['total']} | "
                    f"IS {r['recognition']['IS']['rec']}/{r['recognition']['IS']['total']} | "
                    f"CF {r['recognition']['CF']['rec']}/{r['recognition']['CF']['total']}\n")
            missing = []
            for stmt in ['BS', 'IS', 'CF']:
                m = r['recognition'][stmt]['missing']
                if m:
                    missing.append(f"{stmt}: {m}")
            if missing:
                f.write(f"  关键科目缺失：{' | '.join(missing)}\n")
            f.write(f"  8 个真实性信号：\n")
            for s in r['auth']:
                v = s['value']
                v_str = f"{v:.4f}" if isinstance(v, float) else str(v)
                f.write(f"    {s['rule_id']:34s} = {v_str:>12s} | {s['status']:<14s} ({s['label']})\n")
            f.write(f"  综合判定：{r['summary']['level']}（高风险 {r['summary']['high_risk']} | 关注 {r['summary']['attention']}）\n")

    print(f"\n✅ 报告已写：")
    print(f"   {txt_path}")
    print(f"   {json_path}")


if __name__ == "__main__":
    main()
