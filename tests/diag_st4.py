# -*- coding: utf-8 -*-
"""ST 卓然诊断 4: 找出真利润表和真现金流量表的位置"""
import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')

import re
import fitz
from app.pdf.page_locator import _page_text, _KNOWN_SUBJECTS, _STRONG_INDICATORS

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)
total = len(doc)

_re_number = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")

# 找真利润表
print('=' * 60)
print('【合并利润表】所有 fallback 候选页（含强标志+3+科目+数值+表格）')
print('=' * 60)
known_subjects = _KNOWN_SUBJECTS['合并利润表']
strong_indicators = _STRONG_INDICATORS['合并利润表']
print(f'已知科目: {known_subjects}')
print(f'强标志: {strong_indicators}')
all_candidates = []
for i in range(total):
    text = _page_text(doc, i)
    if not text:
        continue
    if not any(s in text for s in strong_indicators):
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
            all_candidates.append((i + 1, len(hits), hits, n_tables, text[:150].replace(chr(10), ' | ')))

print(f'找到 {len(all_candidates)} 个 fallback 候选页：')
for page, nhits, hits, nt, preview in all_candidates[:10]:
    print(f'  页{page}: 命中{nhits}科目, 表格{nt}个')
    print(f'    命中科目: {hits}')
    print(f'    预览: {preview}')

# 找真现金流量表
print('\n' + '=' * 60)
print('【合并现金流量表】所有 fallback 候选页（含强标志+3+科目+数值+表格）')
print('=' * 60)
known_subjects = _KNOWN_SUBJECTS['合并现金流量表']
strong_indicators = _STRONG_INDICATORS['合并现金流量表']
print(f'已知科目: {known_subjects}')
print(f'强标志: {strong_indicators}')
all_candidates = []
for i in range(total):
    text = _page_text(doc, i)
    if not text:
        continue
    if not any(s in text for s in strong_indicators):
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
            all_candidates.append((i + 1, len(hits), hits, n_tables, text[:150].replace(chr(10), ' | ')))

print(f'找到 {len(all_candidates)} 个 fallback 候选页：')
for page, nhits, hits, nt, preview in all_candidates[:10]:
    print(f'  页{page}: 命中{nhits}科目, 表格{nt}个')
    print(f'    命中科目: {hits}')
    print(f'    预览: {preview}')

# 检查 145-155 页内容（这是真正的三大表连续位置）
print('\n' + '=' * 60)
print('【检查 145-155 页内容】三大表实际所在位置')
print('=' * 60)
for pi in range(144, 160):  # 145-160 页 (0-based: 144-159)
    if pi >= total:
        break
    text = _page_text(doc, pi)
    # 找标题
    has_bs = '合并资产负债表' in text
    has_is = '合并利润表' in text
    has_cf = '合并现金流量表' in text
    has_bs_data = '资产总计' in text
    has_is_data = '营业收入' in text and '营业成本' in text
    has_cf_data = '经营活动产生的现金流量净额' in text or '现金及现金等价物' in text
    print(f'页{pi+1}: BS标题={has_bs} IS标题={has_is} CF标题={has_cf} BS数据={has_bs_data} IS数据={has_is_data} CF数据={has_cf_data}')
    if has_bs or has_is or has_cf or has_bs_data or has_cf_data:
        print(f'  前150字符: {text[:150].replace(chr(10), " | ")}')

doc.close()
