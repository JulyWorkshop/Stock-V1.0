import sys
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\ffa')
sys.path.insert(0, r'C:\Users\歌飛\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6aa92708ddba2d00ae4aa23d\pdf_libs')
import fitz
from app.pdf.page_locator import _page_text

path = r'c:\Users\歌飛\.trae-cn\attachments\6aa92708ddba2d00ae4aa240\f32193f2-0ebb-4d04-b19a-f884258f4f31_6f1783bc-e293-4624-bf62-63919bc06daa__ST卓然：2025年年度报告.pdf'
doc = fitz.open(path)

# 检查第143-155页
print('=== 检查第143-155页 ===')
for pi in range(142, 155):
    text = _page_text(doc, pi)
    has_bs_title = '资产负债表' in text
    has_is_title = '利润表' in text
    has_cf_title = '现金流量表' in text
    has_期末 = '期末余额' in text
    has_期初 = '期初余额' in text
    has_本期 = '本期金额' in text
    has_上期 = '上期金额' in text
    has_货币资金 = '货币资金' in text
    has_营业收入 = '营业收入' in text
    has_经营活动 = '经营活动' in text
    has_资产总计 = '资产总计' in text
    # 有多少表格
    tables = doc[pi].find_tables()
    n_tables = len(tables.tables) if tables and tables.tables else 0
    print(f'页{pi+1}: BS={has_bs_title} IS={has_is_title} CF={has_cf_title} 期末={has_期末} 货币={has_货币资金} 营收={has_营业收入} 经营={has_经营活动} 资产总计={has_资产总计} 表格数={n_tables}')
    if has_货币资金 or has_资产总计 or has_期末:
        print(f'  前150字符: {text[:150].replace(chr(10), " | ")}')

doc.close()
