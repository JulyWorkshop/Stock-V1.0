# -*- coding: utf-8 -*-
"""
ST 卓然深度诊断：
1. 找出所有满足 fallback 条件（含3+已知科目+数值+表格）的页面
2. 显示每个候选页的科目命中数、表格数、页首字符
3. 检查真正的资产负债表页（含"资产总计"）在哪里
"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import re
import fitz
from app.pdf.page_locator import _page_text, _KNOWN_SUBJECTS, _STATEMENT_START_KEYWORDS, _NEXT_STATEMENT_KEYWORDS

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)
total = len(doc)
print(f'PDF 总页数: {total}')

_re_number = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")

# ============= 1. 扫描所有页面，找出所有满足 fallback 条件的页面 =============
print('\n' + '=' * 60)
print('【合并资产负债表】所有 fallback 候选页（含3+已知科目 + 数值 + 表格）')
print('=' * 60)
known_subjects = _KNOWN_SUBJECTS['合并资产负债表']
all_candidates = []
for i in range(total):
    text = _page_text(doc, i)
    if not text:
        continue
    hits = [s for s in known_subjects if s in text]
    if len(hits) >= 3:
        has_number = _re_number.search(text) is not None
        if not has_number:
            continue
        try:
            tables = doc[i].find_tables()
            n_tables = len(tables.tables) if tables and tables.tables else 0
        except Exception:
            n_tables = 0
        if n_tables > 0:
            all_candidates.append((i + 1, len(hits), hits, n_tables, text[:120].replace(chr(10), ' | ')))

print(f'找到 {len(all_candidates)} 个 fallback 候选页：')
for page, nhits, hits, nt, preview in all_candidates:
    print(f'  页{page}: 命中{nhits}科目, 表格{nt}个')
    print(f'    命中科目: {hits}')
    print(f'    预览: {preview}')

# ============= 2. 找含"资产总计"的页面（真资产负债表标志） =============
print('\n' + '=' * 60)
print('含"资产总计"的页面（真资产负债表强标志）')
print('=' * 60)
for i in range(total):
    text = _page_text(doc, i)
    if '资产总计' in text:
        hits = [s for s in known_subjects if s in text]
        tables = doc[i].find_tables()
        n_tables = len(tables.tables) if tables and tables.tables else 0
        print(f'页{i+1}: 命中{len(hits)}科目 表格{n_tables}个')
        print(f'  预览: {text[:200].replace(chr(10), " | ")}')

# ============= 3. 找含"合并资产负债表"标题的页面 =============
print('\n' + '=' * 60)
print('含"合并资产负债表"关键词的页面')
print('=' * 60)
for i in range(total):
    text = _page_text(doc, i)
    if '合并资产负债表' in text:
        print(f'页{i+1}: {text[:200].replace(chr(10), " | ")}')

# ============= 4. 检查审计报告占用范围 =============
print('\n' + '=' * 60)
print('审计报告特征词出现的页面范围')
print('=' * 60)
audit_keywords = ["审计报告", "保留意见", "无法表示意见", "拒绝表示意见",
    "否定意见", "天职业字", "会计师事务所", "审计范围限制"]
audit_pages = []
for i in range(total):
    text = _page_text(doc, i)
    if any(akw in text for akw in audit_keywords):
        audit_pages.append(i + 1)
if audit_pages:
    print(f'审计报告特征词出现在第 {audit_pages[0]} - {audit_pages[-1]} 页（共 {len(audit_pages)} 页）')

doc.close()
