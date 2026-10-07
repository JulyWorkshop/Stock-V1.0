import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')
import fitz
from app.pdf.page_locator import locate_statement_pages, _page_text, _KNOWN_SUBJECTS, _find_statement_start_page

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)
total = len(doc)
print(f'PDF 总页数: {total}')

# 1. 测试各报表的起始页定位
for stmt in ['合并资产负债表', '合并利润表', '合并现金流量表']:
    start = _find_statement_start_page(doc, stmt)
    print(f'\n=== {stmt} 起始页定位 ===')
    print(f'  _find_statement_start_page 返回: {start}')
    if start:
        page = doc[start - 1]
        text = _page_text(doc, start - 1)
        print(f'  页{start} 前200字符: {text[:200]}')
        # 检查这页是否含已知科目
        known = _KNOWN_SUBJECTS.get(stmt, [])
        hits = [s for s in known if s in text]
        print(f'  已知科目命中: {hits}')

# 2. 测试完整页范围
for stmt in ['合并资产负债表', '合并利润表', '合并现金流量表']:
    r = locate_statement_pages(path, stmt)
    print(f'\n{stmt} 完整范围: {r}')

# 3. 找到所有含"合并资产负债表"的页面
print('\n=== 所有含"合并资产负债表"的页面 ===')
for i in range(total):
    text = _page_text(doc, i)
    if '合并资产负债表' in text:
        # 看这页前100字符
        print(f'  页{i+1}: {text[:100].replace(chr(10), " | ")}')

# 4. 找到所有含"合并利润表"的页面
print('\n=== 所有含"合并利润表"的页面 ===')
for i in range(total):
    text = _page_text(doc, i)
    if '合并利润表' in text:
        print(f'  页{i+1}: {text[:100].replace(chr(10), " | ")}')

# 5. 找含"营业收入"且含"营业成本"的页面
print('\n=== 含"营业收入"+"营业成本"的页面 ===')
for i in range(total):
    text = _page_text(doc, i)
    if '营业收入' in text and '营业成本' in text:
        print(f'  页{i+1}: {text[:150].replace(chr(10), " | ")}')
        # 看是否有表格
        tables = doc[i].find_tables()
        if tables and tables.tables:
            print(f'    表格数: {len(tables.tables)}')
        break  # 只看第一个

doc.close()
