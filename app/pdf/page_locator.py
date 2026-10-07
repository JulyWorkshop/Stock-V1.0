# -*- coding: utf-8 -*-
"""
在年报 PDF 中定位三大报表（合并资产负债表 / 合并利润表 / 合并现金流量表）
的页码范围。

返回 (起始页, 结束页)，1-based。找不到返回 None。

实现思路：
- 用 fitz.open 打开 PDF
- 逐页 get_text("text") 搜索关键词
- 合并资产负债表关键词："合并资产负债表"（注意可能写成"合并资产负债表（期末）"等）
- 起始页 = 第一次出现"合并资产负债表"标题的页
- 结束页 = 下一页出现"合并利润表"或"母公司资产负债表"前的最后一页
- 至少返回 1 页（单页报表也可能）
"""
import os
import sys

# 接入本地 PyMuPDF 库
_LIB_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..",
    "pdf_libs",
)
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))

import fitz  # PyMuPDF  # noqa: E402


# 不同报表的"起始标题关键词"——用于定位起始页
_STATEMENT_START_KEYWORDS = {
    "合并资产负债表": ["合并资产负债表"],
    "合并利润表": ["合并利润表"],
    "合并现金流量表": ["合并现金流量表"],
}

# 任何一种"下一个报表/母公司表"的关键词——用于定位结束页
_NEXT_STATEMENT_KEYWORDS = [
    "合并利润表",
    "合并现金流量表",
    "合并所有者权益变动表",
    "母公司资产负债表",
    "母公司利润表",
    "母公司现金流量表",
    "所有者权益变动表",
]


def _page_text(doc, page_index_zero_based: str) -> str:
    """安全地提取某页文本。"""
    try:
        return doc[page_index_zero_based].get_text("text") or ""
    except Exception:
        return ""


# 各报表的已知科目名——用于确认找到了真正的表格页（而非会计政策文字页）
_KNOWN_SUBJECTS = {
    "合并资产负债表": [
        # 资产类
        "货币资金", "应收账款", "存货", "固定资产", "预付款项",
        # 负债类
        "短期借款", "应付账款", "应付票据", "预收款项", "合同负债",
        "一年内到期的非流动负债", "长期借款", "应付债券",
        "负债合计", "负债总计",
        # 权益类
        "实收资本", "股本", "资本公积", "盈余公积", "未分配利润",
        "所有者权益合计", "股东权益合计",
        # 总计
        "资产总计", "资产合计", "负债和所有者权益",
        "负债和股东权益",
    ],
    "合并利润表": ["营业收入", "营业成本", "净利润", "营业利润", "利润总额", "管理费用", "销售费用"],
    "合并现金流量表": ["经营活动", "投资活动", "筹资活动", "现金流量净额", "现金及现金等价物"],
}


# 不同报表的"强标志"——必须出现的合计/总计科目，证明这是真正的报表数据页
# 用于区分"管理层讨论中的财务摘要表"和真正的资产负债表
_STRONG_INDICATORS = {
    "合并资产负债表": ["资产总计", "资产合计", "负债合计", "负债总计",
                      "负债和所有者权益", "负债和股东权益"],
    "合并利润表": ["营业收入", "净利润", "营业利润", "利润总额"],
    "合并现金流量表": ["现金流量净额", "现金及现金等价物"],
}


# fallback 退路排除词——含这些词的页面不作为真报表起始页
# 用于排除：母公司报表、管理层讨论中的变动分析、分部报告、补充资料等
# 这些页面可能命中科目但不是合并报表数据页
_FALLBACK_EXCLUDE_KEYWORDS = {
    "合并资产负债表": [
        "母公司资产负债表",  # 排除母公司资产负债表（精确匹配，避免交叉引用误排除）
        "变动原因",  # 排除管理层讨论（"变动原因说明"的更宽匹配）
        "主要子公司",
        "分部间抵销",
        "补充资料",
        "分部报告",
    ],
    "合并利润表": [
        "母公司利润表",  # 排除母公司利润表（如 ST 卓然页 149）
        "变动原因",  # 排除管理层讨论（修复大唐药业页 15 "变动原因是" 匹配）
        "利润构成",  # 排除管理层讨论中的"利润构成"摘要表（如大唐药业页 15）
        "主要子公司",
        "分部间抵销",  # 排除分部报告
        "补充资料",
        "分部报告",
    ],
    "合并现金流量表": [
        "母公司现金流量表",  # 精确匹配，避免交叉引用"母公司"误排除
        "变动原因",  # 排除管理层讨论（如 ST 卓然页 53）
        "本期比上年",  # 排除管理层讨论中的现金流摘要表（如贵州茅台页 11 "本期比上年同期增减"）
        "主要子公司",
        "分部间抵销",
        "补充资料",  # 排除补充资料（如 ST 卓然页 251）
        "分部报告",
        # 补充资料特征词（"将净利润调节为经营活动现金流量"项目，只在补充资料中出现）
        "固定资产折旧",  # 补充资料中"固定资产折旧、油气资产折耗、生产性生物资产折旧"
        "油气资产折耗",
        "生产性生物资产折旧",
        "使用权资产摊销",
    ],
}


def _get_max_table_rows(page) -> int:
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


# fallback 要求的最低表格行数——真三大表都至少 15 行，管理层讨论摘要表通常只有几行
_FALLBACK_MIN_TABLE_ROWS = 15


def _find_statement_start_page(doc, statement_type: str) -> int | None:
    """
    查找某报表的起始页（1-based）。

    查找规则（按优先级）：
    1. 页面含报表标题关键词 + 已知科目名 + 含数值 + 含强标志 → 强匹配，立即返回
    2. 页面含报表标题关键词 + 表头特征字样 + 含数值 → 中匹配
    3. 退路：遍历所有页面，收集所有"含强标志 + 已知科目 ≥3 + 数值 + 表格"的候选页，
       选科目命中数最多的页面（修复 ST 卓然标题在过渡页被排除的问题）
    4. 都不满足，返回最后一次标题命中页（最弱退路）

    排除条件（防止审计报告/附注文字页误命中）：
    - 含审计报告特征词（"审计报告""保留意见""无法表示意见"等）→ 标题匹配阶段跳过
    - 不含逗号分隔数值（纯文字描述页）→ 不做强匹配
    - 退路要求含"强标志"（如"资产总计"）→ 排除管理层讨论中的财务摘要表
    """
    import re as _re

    keywords = _STATEMENT_START_KEYWORDS.get(statement_type, [statement_type])
    known_subjects = _KNOWN_SUBJECTS.get(statement_type, [])
    strong_indicators = _STRONG_INDICATORS.get(statement_type, [])
    fallback_excludes = _FALLBACK_EXCLUDE_KEYWORDS.get(statement_type, [])
    # 表头特征字样：用于排除目录页和会计政策文字页
    header_hints = [
        "期末余额", "期初余额", "本期金额", "上期金额",
        "本期发生额", "上期发生额", "本年金额", "上年金额",
        # 部分年报（如中国神华）用"附注"作为列头，用"金额单位"标注单位
        "金额单位", "附注",
    ]
    # 审计报告特征词——含这些词的页面直接跳过，不作为报表起始页
    audit_keywords = [
        "审计报告", "保留意见", "无法表示意见", "拒绝表示意见",
        "否定意见", "天职业字", "会计师事务所", "审计范围限制",
        "审计证据", "替代性程序", "项目合伙人", "中国注册会计师",
    ]
    # 数值正则：匹配逗号分隔的数值（如 1,234,567.89 或 123,456.78）
    _re_number = _re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")

    last_hit_page = None  # 最弱退路：标题命中页（可能是审计报告中的交叉引用）
    # 退路2：收集所有"含强标志+科目+表格"的候选页
    # 修复 ST 卓然：原来只取第一个候选，导致定位到第 57 页（管理层摘要表）而非第 145 页（真资产负债表）
    fallback_candidates = []  # [(page, subject_hits_count), ...]

    for i in range(len(doc)):
        text = _page_text(doc, i)
        if not text:
            continue
        # 命中报表标题
        title_hit = any(kw in text for kw in keywords)
        if title_hit:
            # 排除审计报告页
            if any(akw in text for akw in audit_keywords):
                continue

            # 检查页面是否含数值（排除纯文字描述页）
            has_number = _re_number.search(text) is not None
            if not has_number:
                continue

            # 强匹配：页面含已知科目名 ≥3 + 含表头特征字样 + 含强标志
            # 要求 ≥3 个已知科目命中，避免交叉引用误命中
            # （如 ST 卓然页 146 是资产负债表第 2 页但含"营业收入"作为交叉引用）
            has_header = any(h in text for h in header_hints)
            has_strong = any(s in text for s in strong_indicators)
            subject_hits_count = sum(1 for s in known_subjects if s in text) if known_subjects else 0
            if has_header and subject_hits_count >= 3 and has_strong:
                return i + 1
            # 中匹配：页面含表头特征字样 + 含强标志 + 含 ≥3 已知科目
            # （放宽但不放过纯标题页/交叉引用页）
            if has_header and has_strong and subject_hits_count >= 3:
                return i + 1
            # 注：删除原"中匹配2：含已知科目+含强标志"——条件太宽松
            # 页面含 1 个已知科目作为交叉引用就会误命中（如 ST 卓然页 146 是资产负债表第 2 页
            # 但含"营业收入"作为交叉引用）。让 fallback 候选处理这种情况（要求 ≥3 科目+表格行数）。

            # last_hit_page 退路：要求含强标志 + 表格行数 ≥15
            # （避免审计报告中的交叉引用误命中，如 ST 卓然页 146 是资产负债表第 2 页但含"合并利润表"作为交叉引用）
            if has_strong:
                max_rows = _get_max_table_rows(doc[i])
                if max_rows >= _FALLBACK_MIN_TABLE_ROWS:
                    last_hit_page = i + 1

        # 退路2：页面含强标志 + 已知科目 ≥3 + 有数值 + 有表格结构 + 不含排除词 + 表格行数 ≥15
        # （用于ST卓然等标题格式特殊或标题在过渡页被排除的年报）
        # 关键改进1：要求含"强标志"（如资产总计），避免管理层讨论中的财务摘要表误命中
        # 关键改进2：排除"母公司xxx""变动原因说明""补充资料"等作为页面主标题的页面
        #   注意：只检查页面前 200 字符内的排除词，避免页面底部的下表标题（如 ST 卓然页 152
        #   底部含"母公司现金流量表"作为下一表的开始）误排除
        # 关键改进3：收集所有候选，选科目命中数最多（修复 ST 卓然页 145 vs 页 57 的问题）
        # 关键改进4：表格行数 ≥15，避免管理层讨论中的小表格误命中
        if strong_indicators and any(s in text for s in strong_indicators):
            # 排除非合并报表/管理层讨论/补充资料页面（只检查页面前 200 字符内的排除词）
            text_header = text[:200]
            if fallback_excludes and any(ex in text_header for ex in fallback_excludes):
                continue  # 跳过含排除词（作为页面主标题）的页面
            if known_subjects:
                subject_hits_list = [s for s in known_subjects if s in text]
                if len(subject_hits_list) >= 3:
                    has_number = _re_number.search(text) is not None
                    if has_number:
                        # 检查是否有表格结构 + 行数 ≥15
                        max_rows = _get_max_table_rows(doc[i])
                        if max_rows >= _FALLBACK_MIN_TABLE_ROWS:
                            fallback_candidates.append((i + 1, len(subject_hits_list)))

    # fallback 候选选择策略（按报表类型区分）：
    # - 资产负债表：选最早的（合并报表第一页含资产类科目如货币资金/应收账款，
    #   在母公司报表之前。之前选科目命中最多的导致选到母公司报表页）
    # - 利润表/现金流量表：选科目命中最多的（避免选到管理层讨论摘要表，
    #   摘要表可能出现在更早的页面但科目命中数较少）
    if fallback_candidates:
        if statement_type == "合并资产负债表":
            fallback_candidates.sort(key=lambda x: x[0])  # 按页码升序
        else:
            fallback_candidates.sort(key=lambda x: x[1], reverse=True)  # 按科目命中数降序
        return fallback_candidates[0][0]

    # 都不满足，返回最后一次标题命中页（最弱退路）
    return last_hit_page


def locate_statement_pages(pdf_path: str, statement_type: str) -> tuple[int, int] | None:
    """
    返回 (起始页, 结束页)，1-based。找不到返回 None。
    statement_type 取 StatementType.value（如 "合并资产负债表"）。

    结束页判定规则（修复版）：
    - 仅当某页同时满足以下两个条件时，才视为"下一个报表的起始页"：
      1. 含下一个报表/母公司表的关键词
      2. 不含当前报表的任何已知科目（说明确实已离开当前报表）
    - 否则（如页面含"合并利润表"交叉引用但同时含"资本公积"），仍视为当前报表的延续页
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[page_locator] 打开 PDF 失败: {pdf_path} -> {e}")
        return None

    try:
        total_pages = len(doc)
        start_page = _find_statement_start_page(doc, statement_type)
        if start_page is None:
            return None

        # 向前一页扫描，处理跨页表
        # 修复 ST 卓然：利润表起始在页 146 底部（"合并利润表"标题+"一、营业收入"），
        # 但 fallback 选了页 147（命中 6 个利润表科目，比页 146 命中 1 个多）
        # 修复方案：只当前一页含"合并xxx表"标题时才向前一页
        #   避免误扩展到管理层讨论页（如大唐药业利润表范围 (14, 63) 错误扩大）
        # 安全性：table_parser 的 _find_statement_tables 已过滤不含 known_subjects 的表格
        if statement_type in ("合并利润表", "合并现金流量表") and start_page > 1:
            prev_text = _page_text(doc, start_page - 2)  # start_page-1 是 1-based 前一页，转 0-based
            # 修复茅台 2018：合并利润表标题在 p57，但表格数据从 p56 开始（p56 是无表头延续行）。
            # 原条件仅"前一页含合并利润表等标题"才向前扩展，但 p56 文本不含"合并利润表"字样，
            # 导致 start_page 错定为 57，漏掉 p56 的"1.归属于母公司股东的净利润"等关键科目。
            # 新增：前一页若含当前报表的多个已知科目（≥3），也视为延续页，向前扩展 1 页。
            known_subjects_for_type = _KNOWN_SUBJECTS.get(statement_type, [])
            prev_subject_hits = (
                sum(1 for s in known_subjects_for_type if s in prev_text)
                if known_subjects_for_type
                else 0
            )
            if statement_type in prev_text or prev_subject_hits >= 3:
                start_page = start_page - 1

        # 当前报表的已知科目——用于判断某页是否仍属于当前报表
        known_subjects = _KNOWN_SUBJECTS.get(statement_type, [])
        # 结束关键词（排除当前报表自身）
        keywords_for_end = [kw for kw in _NEXT_STATEMENT_KEYWORDS if kw != statement_type]

        # 母公司报表标题——出现在页面前部时强制结束（避免母公司报表被当作合并报表延续）
        mother_keywords = ["母公司资产负债表", "母公司利润表", "母公司现金流量表"]

        end_page = total_pages
        for i in range(start_page, total_pages):  # i 是 0-based
            text = _page_text(doc, i)
            if not text:
                continue
            # 跳过起始页自身
            if i + 1 == start_page:
                continue
            # 强制结束：页面顶部含"母公司xxx表"标题（说明进入母公司报表，不是合并报表延续）
            # 修复 ST 卓然：页 149 含"母公司利润表"作为页面主标题，但含利润表科目导致 still_in_statement=True
            # → 之前不会结束 → 母公司利润表被当作合并利润表延续解析，导致营业收入等值取错
            text_header = text[:200]
            if any(mk in text_header for mk in mother_keywords):
                end_page = i  # 该页前一页即结束页
                break
            # 该页是否仍含当前报表的已知科目？
            still_in_statement = known_subjects and any(s in text for s in known_subjects)
            # 该页是否含下一个报表关键词？
            has_next_keyword = any(kw in text for kw in keywords_for_end)
            # 只有当"含下一个报表关键词"且"不含当前报表科目"时，才确认为结束边界
            if has_next_keyword and not still_in_statement:
                end_page = i  # 该页前一页即结束页（i 是 0-based）
                break
            # 若含下一个报表关键词但同时含当前报表科目，说明是交叉引用，继续扫描
            # 若不含下一个报表关键词，继续扫描
        # 至少返回 1 页
        if end_page < start_page:
            end_page = start_page
        return (start_page, end_page)
    finally:
        try:
            doc.close()
        except Exception:
            pass
