# -*- coding: utf-8 -*-
"""
诊断脚本 - 找出每家公司每张报表中"标准科目未识别"的科目，
并扫描 PDF 报表页范围内所有含数字的行，帮助定位 PDF 原文科目名。

输出：
  1. 每家公司每张报表的识别率
  2. 未识别的标准科目列表
  3. 对每个未识别科目，搜索 PDF 页面文本中是否出现其别名/近义写法
  4. dump 报表页范围内所有"含数字的行"（最多前 300 行/公司/报表），
     便于人工核查科目名变体
"""
import os
import re
import sys

sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz  # PyMuPDF  # noqa: E402

from app.pdf.parsers.table_parser import parse_statement_by_table  # noqa: E402
from app.pdf.page_locator import locate_statement_pages  # noqa: E402
from app.pdf.subject_alias import (  # noqa: E402
    SUBJECT_ALIASES_BY_STATEMENT,
    list_standard_subjects,
    standardize_subject_name,
)

TEST_CASES = [
    ('ST卓然', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf', 2025),
    ('大唐药业', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf', 2025),
    ('贵州茅台', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf', 2018),
    ('天键股份', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\1ebd8903-d4f6-410e-873a-25e36b1cc605_58c3aff0-bb5d-4f19-96af-8b36d1a8bac0_天键股份：2025年年度报告（更正后）.pdf', 2025),
    ('岩山科技', r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\91132a2d-d9f0-4907-bdca-6664b8f56b52_075d5e45-a1da-4258-aa6b-7307074a9136_岩山科技：2025年年度报告（更正后）.pdf', 2025),
]

# 含数字行的正则（数字+可能逗号+可能小数）
NUM_LINE_RE = re.compile(r"\d[\d,]*\.?\d*")

# 科目名候选正则（中文开头，后接中文/括号，不含数字的行段）
SUBJECT_NAME_CHAR = re.compile(r"[\u4e00-\u9fa5（）\(\)、、：:]+")


def _extract_page_lines(doc, start_page: int, end_page: int) -> list[tuple[int, str]]:
    """提取报表页范围内所有文本行"""
    lines: list[tuple[int, str]] = []
    for page_idx in range(start_page - 1, end_page):
        if page_idx >= len(doc):
            break
        page = doc[page_idx]
        text = page.get_text("text")
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append((page_idx + 1, line))
    return lines


def _find_alias_in_pages(
    aliases: list[str],
    page_lines: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """在页面行中搜索 alias 出现的行"""
    hits: list[tuple[int, str]] = []
    for alias in aliases:
        ac = alias.replace(" ", "").replace("\u3000", "")
        if len(ac) < 3:
            continue
        for page_no, line in page_lines:
            lc = line.replace(" ", "").replace("\u3000", "")
            if ac in lc:
                hits.append((page_no, line))
    return hits


def _dump_subject_candidate_lines(
    page_lines: list[tuple[int, str]],
    max_lines: int = 300,
) -> list[tuple[int, str]]:
    """挑出含数字且行首是中文的行（疑似科目行）"""
    candidates: list[tuple[int, str]] = []
    for page_no, line in page_lines:
        # 必须含数字
        if not NUM_LINE_RE.search(line):
            continue
        # 行长度限制（避免附注散文）
        if len(line) > 160:
            continue
        # 行首需含中文字符（科目名候选）
        if not SUBJECT_NAME_CHAR.search(line[:10]):
            continue
        candidates.append((page_no, line))
        if len(candidates) >= max_lines:
            break
    return candidates


def main():
    output_lines: list[str] = []

    def out(s: str = ""):
        print(s)
        output_lines.append(s)

    for name, path, year in TEST_CASES:
        out("")
        out("=" * 70)
        out(f"【{name}】 {year} 年报")
        out("=" * 70)

        for stmt_type in ["合并资产负债表", "合并利润表", "合并现金流量表"]:
            page_range = locate_statement_pages(path, stmt_type)
            if page_range is None:
                out(f"\n--- {stmt_type}: ❌ 未定位到 ---")
                continue

            items = parse_statement_by_table(path, year, stmt_type, name)
            all_std = list_standard_subjects(stmt_type)
            recognized = {it.name for it in items if it.is_recognized}
            missing = [s for s in all_std if s not in recognized]
            rec_count = len(recognized)

            out("")
            out(f"--- {stmt_type} {page_range}: {rec_count}/{len(all_std)} 已识别 ---")
            if not missing:
                out("  ✅ 全部识别")
                continue

            out(f"  ❌ 未识别 {len(missing)} 个标准科目:")
            aliases_map = SUBJECT_ALIASES_BY_STATEMENT.get(stmt_type, {})

            # 打开 PDF，提取页面文本
            try:
                doc = fitz.open(path)
            except Exception as e:
                out(f"  [ERROR] 打开 PDF 失败: {e}")
                continue

            try:
                page_lines = _extract_page_lines(doc, page_range[0], page_range[1])
            finally:
                try:
                    doc.close()
                except Exception:
                    pass

            for std in missing:
                aliases = aliases_map.get(std, [])
                out("")
                out(f"  □ 标准科目: {std}")
                out(f"    当前别名: {aliases}")
                hits = _find_alias_in_pages(aliases, page_lines)
                if hits:
                    out(f"    PDF 中出现的行 (共 {len(hits)} 条):")
                    for page_no, line in hits[:5]:
                        out(f"      p{page_no}: {line}")
                else:
                    out(f"    ⚠ PDF 页面文本中未出现任何别名")

        # 末尾 dump 一家公司每张报表的前 50 条候选科目行
        out("")
        out(f"=== {name} 候选科目行 dump (含数字+中文行首) ===")
        for stmt_type in ["合并资产负债表", "合并利润表", "合并现金流量表"]:
            page_range = locate_statement_pages(path, stmt_type)
            if page_range is None:
                continue
            try:
                doc = fitz.open(path)
            except Exception:
                continue
            try:
                page_lines = _extract_page_lines(doc, page_range[0], page_range[1])
            finally:
                try:
                    doc.close()
                except Exception:
                    pass
            candidates = _dump_subject_candidate_lines(page_lines, max_lines=50)
            out("")
            out(f"--- {stmt_type} {page_range} 前 50 候选行 ---")
            for page_no, line in candidates:
                out(f"  p{page_no}: {line}")

    # 写入文件
    out_path = os.path.join(os.path.dirname(__file__), "diag_missing_subjects_output.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\n[OK] 诊断报告已写入: {out_path}")


if __name__ == "__main__":
    main()
