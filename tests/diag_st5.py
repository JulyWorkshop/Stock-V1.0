# -*- coding: utf-8 -*-
"""ST 卓然诊断 5: 检查候选页表格行数，找出真表与摘要表的区别"""
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


def get_max_rows(page):
    """获取页面中最大表格的行数"""
    try:
        tables = page.find_tables()
        if not tables or not tables.tables:
            return 0
        max_rows = 0
        for tbl in tables.tables:
            try:
                rows = tbl.extract()
                if rows and len(rows) > max_rows:
                    max_rows = len(rows)
            except Exception:
                pass
        return max_rows
    except Exception:
        return 0


for stmt_type in ['合并资产负债表', '合并利润表', '合并现金流量表']:
    print('=' * 60)
    print(f'【{stmt_type}】所有 fallback 候选页详情')
    print('=' * 60)
    known_subjects = _KNOWN_SUBJECTS[stmt_type]
    strong_indicators = _STRONG_INDICATORS[stmt_type]
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
            max_rows = get_max_rows(doc[i])
            if max_rows > 0:
                all_candidates.append((i + 1, len(hits), max_rows, hits))

    print(f'找到 {len(all_candidates)} 个 fallback 候选页：')
    # 按行数排序
    all_candidates.sort(key=lambda x: x[2], reverse=True)
    for page, nhits, nrows, hits in all_candidates[:8]:
        print(f'  页{page}: 命中{nhits}科目, 表格{nrows}行')
        print(f'    命中科目: {hits}')
    # 按命中数排序
    print('\n  --- 按命中数排序 ---')
    all_candidates.sort(key=lambda x: x[1], reverse=True)
    for page, nhits, nrows, hits in all_candidates[:5]:
        print(f'  页{page}: 命中{nhits}科目, 表格{nrows}行')

doc.close()
