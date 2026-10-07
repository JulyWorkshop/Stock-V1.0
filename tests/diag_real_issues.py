# -*- coding: utf-8 -*-
"""
诊断 3 个真实未识别问题：
1. 大唐药业利润表范围 (15, 63) 太宽 — 起始页 15 错误
2. 贵州茅台现金流量表范围 (11, 48) 太宽 — 起始页 11 错误
3. 岩山科技利润表缺关键科目 — 可能 mother_keywords 强制结束太早
"""
import sys
import os

sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import fitz
from app.pdf.page_locator import locate_statement_pages, _page_text, _KNOWN_SUBJECTS, _find_statement_start_page, _STRONG_INDICATORS, _FALLBACK_EXCLUDE_KEYWORDS, _get_max_table_rows, _FALLBACK_MIN_TABLE_ROWS

PDFS = {
    '大唐药业': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\e8002895-eff7-430b-b6bc-bdcf7a54910f_a9bb0d7a-c467-4d91-aaf4-7b97ea0a26fc_大唐药业：2025年年度报告.pdf',
    '贵州茅台': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\6790957e-9bea-4ddd-a1a5-9281b77900dc_29e319db-e738-486b-b8e7-b9f899ffe90d_贵州茅台：2018年年度报告.pdf',
    '岩山科技': r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\91132a2d-d9f0-4907-bdca-6664b8f56b52_075d5e45-a1da-4258-aa6b-7307074a9136_岩山科技：2025年年度报告（更正后）.pdf',
}

# ============================================================
# 1. 大唐药业利润表起始页 15 问题
# ============================================================
print('=' * 60)
print('【1. 大唐药业利润表起始页 15 问题】')
print('=' * 60)

path = PDFS['大唐药业']
doc = fitz.open(path)
total = len(doc)

# 找所有含"合并利润表"的页面
print('\n--- 所有含"合并利润表"的页面 ---')
for i in range(total):
    text = _page_text(doc, i)
    if '合并利润表' in text:
        idx = text.find('合并利润表')
        ctx = text[max(0,idx-20):idx+50].replace('\n', ' | ')
        print(f'  页{i+1}: ...{ctx}...')

# 找利润表 fallback 候选页
print('\n--- 利润表 fallback 候选页分析 ---')
stmt = '合并利润表'
strong_indicators = _STRONG_INDICATORS.get(stmt, [])
fallback_excludes = _FALLBACK_EXCLUDE_KEYWORDS.get(stmt, [])
known_subjects = _KNOWN_SUBJECTS.get(stmt, [])
print(f'强标志: {strong_indicators}')
print(f'排除词: {fallback_excludes}')
print(f'已知科目: {known_subjects}')

import re
_re_number = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")
fallback_candidates = []

for i in range(total):
    text = _page_text(doc, i)
    if not text:
        continue
    if strong_indicators and any(s in text for s in strong_indicators):
        text_header = text[:200]
        excluded = False
        if fallback_excludes and any(ex in text_header for ex in fallback_excludes):
            excluded = True
        if known_subjects:
            hits = [s for s in known_subjects if s in text]
            if len(hits) >= 3:
                has_number = _re_number.search(text) is not None
                if has_number:
                    max_rows = _get_max_table_rows(doc[i])
                    if max_rows >= _FALLBACK_MIN_TABLE_ROWS:
                        fallback_candidates.append((i+1, len(hits), max_rows, excluded, text[:80].replace('\n','|')))

print(f'\n所有 fallback 候选页（含被排除的）:')
for p, hits, rows, excl, ctx in fallback_candidates:
    status = '❌被排除' if excl else '✅候选'
    print(f'  页{p} 科目命中={hits} 表格行数={rows} {status} 上下文: {ctx[:60]}')

if fallback_candidates:
    not_excluded = [(p,h,r,ex,c) for p,h,r,ex,c in fallback_candidates if not ex]
    if not_excluded:
        not_excluded.sort(key=lambda x: x[1], reverse=True)
        print(f'\n选中的页: {not_excluded[0][0]} (科目命中={not_excluded[0][1]})')

# 看页 15 内容
print('\n--- 页 15 内容（当前选中的起始页）---')
text15 = _page_text(doc, 14)
print(f'前300字符: {text15[:300]}')
print(f'含强标志: {[s for s in strong_indicators if s in text15]}')
print(f'含已知科目: {[s for s in known_subjects if s in text15]}')
print(f'表格行数: {_get_max_table_rows(doc[14])}')

# 看真正的利润表在哪页
print('\n--- 找含"营业收入"+"营业成本"+"净利润"的页面 ---')
for i in range(total):
    text = _page_text(doc, i)
    if '营业收入' in text and '营业成本' in text and '净利润' in text:
        hits = [s for s in known_subjects if s in text]
        rows = _get_max_table_rows(doc[i])
        print(f'  页{i+1} 科目命中={len(hits)} 表格行数={rows} 前80字符: {text[:80].replace(chr(10),"|")}')

doc.close()

# ============================================================
# 2. 贵州茅台现金流量表起始页 11 问题
# ============================================================
print('\n\n' + '=' * 60)
print('【2. 贵州茅台现金流量表起始页 11 问题】')
print('=' * 60)

path = PDFS['贵州茅台']
doc = fitz.open(path)
total = len(doc)

# 找所有含"合并现金流量表"的页面
print('\n--- 所有含"合并现金流量表"的页面 ---')
for i in range(total):
    text = _page_text(doc, i)
    if '合并现金流量表' in text:
        idx = text.find('合并现金流量表')
        ctx = text[max(0,idx-20):idx+50].replace('\n', ' | ')
        print(f'  页{i+1}: ...{ctx}...')

# 找现金流量表 fallback 候选页
print('\n--- 现金流量表 fallback 候选页分析 ---')
stmt = '合并现金流量表'
strong_indicators = _STRONG_INDICATORS.get(stmt, [])
fallback_excludes = _FALLBACK_EXCLUDE_KEYWORDS.get(stmt, [])
known_subjects = _KNOWN_SUBJECTS.get(stmt, [])

fallback_candidates = []
for i in range(total):
    text = _page_text(doc, i)
    if not text:
        continue
    if strong_indicators and any(s in text for s in strong_indicators):
        text_header = text[:200]
        excluded = False
        if fallback_excludes and any(ex in text_header for ex in fallback_excludes):
            excluded = True
        if known_subjects:
            hits = [s for s in known_subjects if s in text]
            if len(hits) >= 3:
                has_number = _re_number.search(text) is not None
                if has_number:
                    max_rows = _get_max_table_rows(doc[i])
                    if max_rows >= _FALLBACK_MIN_TABLE_ROWS:
                        fallback_candidates.append((i+1, len(hits), max_rows, excluded, text[:80].replace('\n','|')))

print(f'所有 fallback 候选页（含被排除的）:')
for p, hits, rows, excl, ctx in fallback_candidates:
    status = '❌被排除' if excl else '✅候选'
    print(f'  页{p} 科目命中={hits} 表格行数={rows} {status} 上下文: {ctx[:60]}')

if fallback_candidates:
    not_excluded = [(p,h,r,ex,c) for p,h,r,ex,c in fallback_candidates if not ex]
    if not_excluded:
        not_excluded.sort(key=lambda x: x[1], reverse=True)
        print(f'\n选中的页: {not_excluded[0][0]} (科目命中={not_excluded[0][1]})')

# 看页 11 内容
print('\n--- 页 11 内容（当前选中的起始页）---')
text11 = _page_text(doc, 10)
print(f'前300字符: {text11[:300]}')
print(f'含强标志: {[s for s in strong_indicators if s in text11]}')
print(f'含已知科目: {[s for s in known_subjects if s in text11]}')
print(f'表格行数: {_get_max_table_rows(doc[10])}')

# 看真正的现金流量表在哪页
print('\n--- 找含"经营活动"+"投资活动"+"筹资活动"的页面 ---')
for i in range(total):
    text = _page_text(doc, i)
    if '经营活动' in text and '投资活动' in text and '筹资活动' in text:
        hits = [s for s in known_subjects if s in text]
        rows = _get_max_table_rows(doc[i])
        print(f'  页{i+1} 科目命中={len(hits)} 表格行数={rows} 前80字符: {text[:80].replace(chr(10),"|")}')

doc.close()

# ============================================================
# 3. 岩山科技利润表缺关键科目问题
# ============================================================
print('\n\n' + '=' * 60)
print('【3. 岩山科技利润表缺关键科目问题】')
print('=' * 60)

path = PDFS['岩山科技']
doc = fitz.open(path)
total = len(doc)

# 看利润表范围
r = locate_statement_pages(path, '合并利润表')
print(f'\n利润表范围: {r}')

if r:
    start, end = r
    # 看每页的表格内容
    print(f'\n--- 利润表页 {start}-{end} 的表格内容 ---')
    for page_idx in range(start-1, end):
        page = doc[page_idx]
        try:
            table_finder = page.find_tables()
        except Exception:
            continue
        if not table_finder or not table_finder.tables:
            print(f'  页{page_idx+1}: 无表格')
            continue

        for tbl_idx, table in enumerate(table_finder.tables):
            try:
                rows = table.extract()
            except Exception:
                continue
            if not rows:
                continue
            print(f'  页{page_idx+1} 表{tbl_idx+1} ({len(rows)} 行):')
            for ri, row in enumerate(rows):
                row_text = ' '.join(str(c) for c in row if c)
                # 只显示含利润表科目的行
                profit_keywords = ['营业收入', '营业成本', '营业利润', '利润总额', '净利润', '销售费用', '管理费用', '合并利润表']
                if any(kw in row_text for kw in profit_keywords):
                    print(f'    行{ri+1}: {row}')

# 看页 105-107 的文本前 200 字符
print('\n--- 页 105-107 前 200 字符 ---')
for p in [105, 106, 107]:
    if p <= total:
        text = _page_text(doc, p-1)
        print(f'  页{p}: {text[:200].replace(chr(10), " | ")}')

# 检查是否有母公司利润表标题导致提前结束
print('\n--- 检查页 105-110 含"母公司利润表"的位置 ---')
for p in range(105, min(112, total+1)):
    text = _page_text(doc, p-1)
    if '母公司利润表' in text:
        idx = text.find('母公司利润表')
        ctx = text[max(0,idx-30):idx+30].replace('\n', ' | ')
        print(f'  页{p} 含"母公司利润表" 位置={idx} 上下文: ...{ctx}...')

doc.close()
print('\n完成')
