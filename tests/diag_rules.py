# -*- coding: utf-8 -*-
"""诊断脚本：跑三大表解析器 + 22 条规则，验证全流程不报错并打印结果。

用法：
    python -m tests.diag_rules <pdf_dir>
    python -m tests.diag_rules "C:\\...\\测试年报"
"""
import os
import sys
import traceback

_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pdf_libs")
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.company import Company
from app.models.project import AnalysisProject
from app.pdf.importer import import_pdfs
from app.pdf.parsers.balance_sheet import parse_balance_sheet
from app.pdf.parsers.income_statement import parse_income_statement
from app.pdf.parsers.cash_flow import parse_cash_flow
from app.pdf.parsers.fallback_scan import fallback_scan
from app.rules.engine import apply_all, apply_rule
from app.rules.thresholds import load_rules


def _print_per_statement(project: AnalysisProject) -> None:
    """打印三大表识别情况"""
    for stmt_label in ["合并资产负债表", "合并利润表", "合并现金流量表"]:
        years = project.get_years()
        if not years:
            continue
        year = years[-1]
        items = project.get_line_items_by_year(year, stmt_label)
        recognized = [it for it in items if it.is_recognized]
        print(f"\n--- {stmt_label} ({year}) ---")
        print(f"已识别: {len(recognized)}/{len(items)}")
        # 打印关键科目
        for name in ["总资产", "总负债", "货币资金", "存货", "营业收入", "净利润",
                     "归属于母公司股东的净利润", "经营活动产生的现金流量净额"]:
            li = project.get_line_item(year, name, stmt_label)
            if li:
                v = li.value_in_yuan
                print(f"  {name:<30} = {v:>15,.0f} 元  (p{li.source_page})")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python -m tests.diag_rules <pdf_dir>")
        return 2
    pdf_dir = sys.argv[1]
    if not os.path.isdir(pdf_dir):
        print(f"目录不存在: {pdf_dir}")
        return 2

    # 找所有 pdf
    pdf_paths = sorted([
        os.path.join(pdf_dir, f)
        for f in os.listdir(pdf_dir)
        if f.lower().endswith(".pdf")
    ])
    if not pdf_paths:
        print(f"目录中没有 PDF: {pdf_dir}")
        return 2

    print(f"找到 {len(pdf_paths)} 个 PDF")
    for p in pdf_paths:
        print(f"  {os.path.basename(p)}")

    # 1) 校验
    try:
        result = import_pdfs(pdf_paths)
    except Exception as e:
        print(f"import_pdfs 异常: {e}")
        traceback.print_exc()
        return 1

    if result.errors:
        print(f"\n校验错误 ({len(result.errors)}):")
        for err in result.errors:
            print(f"  [{err.code}] {err.message}")
        # 不退出，继续解析

    if not result.reports:
        print("无有效年报，退出")
        return 1

    company = result.reports[0].company
    print(f"\n公司: {company.display_name()}")
    print(f"年份: {[r.year for r in result.reports]}")

    # 2) 三大表解析 + fallback_scan 补漏
    all_items = []
    for rpt in result.reports:
        bs = parse_balance_sheet(rpt.pdf_path, rpt.year, company.name)
        all_items.extend(bs)
        ic = parse_income_statement(rpt.pdf_path, rpt.year, company.name)
        all_items.extend(ic)
        cf = parse_cash_flow(rpt.pdf_path, rpt.year, company.name)
        all_items.extend(cf)
        # 借鉴 workbuddy 策略补漏
        bs_found = {it.name for it in bs if it.is_recognized}
        ic_found = {it.name for it in ic if it.is_recognized}
        cf_found = {it.name for it in cf if it.is_recognized}
        fb_bs = fallback_scan(rpt.pdf_path, rpt.year, "合并资产负债表", bs_found, company.name)
        fb_ic = fallback_scan(rpt.pdf_path, rpt.year, "合并利润表", ic_found, company.name)
        fb_cf = fallback_scan(rpt.pdf_path, rpt.year, "合并现金流量表", cf_found, company.name)
        all_items.extend(fb_bs + fb_ic + fb_cf)
        if fb_bs or fb_ic or fb_cf:
            print(f"\n[fallback] {rpt.year} 年补漏: BS={len(fb_bs)} IC={len(fb_ic)} CF={len(fb_cf)}")

    project = AnalysisProject(
        company=company,
        year_reports=list(result.reports),
        line_items=all_items,
    )

    # 3) 打印识别情况
    _print_per_statement(project)

    # 4) 执行所有 22 条规则
    rules, subject_groups = load_rules()
    print(f"\n========== 执行 {len(rules)} 条规则 ==========")

    errors = 0
    for year in project.get_years():
        print(f"\n>>> 年份: {year}")
        for rule in rules:
            try:
                r = apply_rule(rule, project, year)
                v = r.actual_value
                if isinstance(v, dict):
                    v_str = ", ".join(f"{k}={val:.2%}" if isinstance(val, (int, float)) else f"{k}={val}"
                                       for k, val in v.items() if k != "total_assets")
                elif isinstance(v, (int, float)):
                    v_str = f"{v:.4f}"
                else:
                    v_str = str(v)
                print(f"  [{rule.id:40s}] {r.status.value:15s}  value={v_str}")
            except Exception as e:
                errors += 1
                print(f"  [{rule.id:40s}] ERROR: {type(e).__name__}: {e}")
                traceback.print_exc()

    print(f"\n========== 完成 ==========")
    print(f"总规则执行: {len(rules) * len(project.get_years())}")
    print(f"错误数: {errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
