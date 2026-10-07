# -*- coding: utf-8 -*-
"""
workbuddy 式补漏扫描器 - 借鉴 workbuddy 的 5 大识别策略补漏主解析器漏识别的科目。

借鉴的 5 大策略：
1. 行长度过滤（>160 字符跳过，避免附注散文误识）
2. 跨页延续上下文（active 变量保持报表类型，直到遇到母公司报表标题才重置）
3. 双数值策略（取行末两个数值，第一个=本年，第二个=上年；可补漏当前年和上年数据）
4. 置信度模型（同 key 多次命中保留最高置信度；同页+0.95，跨页延续+0.82，行首匹配+0.02）
5. 跨行拼接（本行无数值时拼下一行再试）
6. 必备科目校验（核心科目缺失发警告）

接口：
    fallback_scan(pdf_path, year, statement_type, already_found, company_name) -> list[LineItem]

设计：
- 输入：PDF 路径、目标年份、报表类型、已识别的标准科目集合（避免重复）
- 输出：补漏的 LineItem 列表（只补 already_found 中不存在的标准科目）
- 内部：在 page_locator 找到的页范围内用更宽松匹配；同时扫描其他页用 active 变量延续
"""
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 接入本地 PyMuPDF 库
_LIB_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..",
    "pdf_libs",
)
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))

import fitz  # PyMuPDF  # noqa: E402

from app.models.line_item import LineItem
from app.models.statements import StatementType
from app.pdf.page_locator import locate_statement_pages
from app.pdf.subject_alias import SUBJECT_ALIASES_BY_STATEMENT, list_standard_subjects
from app.pdf.unit_detector import detect_unit_for_statement


# ============================================================
# 常量
# ============================================================

# 行长度限制：超过此长度的行视为散文附注，跳过
_MAX_LINE_LEN = 160

# 置信度常量（借鉴 workbuddy）
_CONFIDENCE_SAME_PAGE = 0.95    # 同页同类型匹配
_CONFIDENCE_CROSS_PAGE = 0.82   # 跨页延续上下文
_CONFIDENCE_LINE_START_BONUS = 0.02  # 行首完全匹配加分

# 必备科目（缺失就报警告）
_MUST_HAVE = {
    "合并资产负债表": ["总资产", "总负债", "货币资金", "存货", "应收账款"],
    "合并利润表": ["营业收入", "营业成本", "净利润", "归属于母公司股东的净利润"],
    "合并现金流量表": ["经营活动产生的现金流量净额", "销售商品提供劳务收到的现金"],
}

# 报表标题识别
_STATEMENT_KIND_HEADERS = {
    "合并资产负债表": ["合并资产负债表", "资产负债表"],
    "合并利润表": ["合并利润表", "利润表"],
    "合并现金流量表": ["合并现金流量表", "现金流量表"],
}

# 母公司报表标题（遇到就重置上下文）
_PARENT_HEADERS = ["母公司资产负债表", "母公司利润表", "母公司现金流量表"]

# 数值匹配正则（借鉴 workbuddy 的 NUM_RE，支持千分位、括号负数、减号）
_NUM_RE = re.compile(r"(?<![\w.])\(?-?\d[\d,，]*(?:\.\d+)?\)?")


# ============================================================
# 内部数据结构
# ============================================================


@dataclass
class _FoundValue:
    """单次匹配的命中结果"""
    standard: str          # 标准科目名
    value: float           # 当前年数值（元）
    prior_value: Optional[float]  # 上年数值（元），None 表示无
    page: int              # 1-based 页码
    line: str              # 命中行的原文（用于调试）
    confidence: float      # 置信度


def _clean_text(s: str) -> str:
    """借鉴 workbuddy 的 clean_text：去空白 + 统一标点"""
    return re.sub(r"\s+", "", s).replace("，", ",").replace("：", ":")


def _parse_number(token: str) -> Optional[float]:
    """解析单段数字 token（借鉴 workbuddy）"""
    t = token.strip().replace(",", "").replace("，", "")
    neg = t.startswith("(") and t.endswith(")") or t.startswith("（") and t.endswith("）")
    t = t.strip("()（）")
    if t.startswith("-"):
        neg = True
        t = t.lstrip("-")
    if not t:
        return None
    try:
        v = float(t)
        return -v if neg else v
    except ValueError:
        return None


def _choose_two_values(line: str) -> Tuple[Optional[float], Optional[float]]:
    """借鉴 workbuddy 的 choose_two_values：取行末两个数值
    返回 (current, prior)。current 是本年期末余额，prior 是上年期末余额。
    """
    nums = []
    for m in _NUM_RE.finditer(line):
        v = _parse_number(m.group(0))
        if v is not None:
            nums.append((m.group(0), v))
    # 借鉴 workbuddy：优先选 rich numbers（含逗号/小数/绝对值>=1000）
    rich = [(tok, v) for tok, v in nums if "," in tok or "." in tok or abs(v) >= 1000]
    if len(rich) >= 2:
        vals = [v for _, v in rich]
    elif len(nums) >= 2:
        vals = [v for _, v in nums]
    else:
        vals = [v for _, v in nums]
    if not vals:
        return None, None
    if len(vals) >= 2:
        return vals[-2], vals[-1]
    return vals[-1], None


def _detect_statement_kind(page_text: str) -> Optional[str]:
    """识别单页属于哪类报表（借鉴 workbuddy 的 statement_kind）"""
    t = _clean_text(page_text[:2500])
    # 必须含"合并"或独立标题
    for stmt, headers in _STATEMENT_KIND_HEADERS.items():
        for h in headers:
            if h in t:
                return stmt
    return None


def _has_parent_header(page_text: str) -> bool:
    """检测页面是否含母公司报表标题"""
    t = _clean_text(page_text[:500])
    return any(h in t for h in _PARENT_HEADERS)


def _detect_unit_multiplier(page_text: str) -> float:
    """借鉴 workbuddy 的 unit_multiplier：检测单位倍率"""
    t = _clean_text(page_text[:2500])
    if re.search(r"单位[:：]人民币?万元", t) or "单位:万元" in t:
        return 1e4
    if re.search(r"单位[:：]人民币?百万元", t):
        return 1e6
    if re.search(r"单位[:：]人民币?千元", t) or "单位:千元" in t:
        return 1e3
    if re.search(r"单位[:：]人民币?元", t) or "单位:元" in t:
        return 1.0
    return 1.0  # 默认元


def _match_subject_in_line(line_compact: str, statement_type: str) -> Optional[Tuple[str, str]]:
    """行内匹配标准科目（借鉴 workbuddy 的 ALIASES 包含匹配）

    返回 (standard_name, matched_alias) 或 None
    设计：
    - 遍历 SUBJECT_ALIASES_BY_STATEMENT[statement_type] 的所有 alias
    - 用 clean(alias) in line_compact 包含匹配
    - 不调用 standardize_subject_name（其包含匹配有长度限制，会漏掉部分场景）
    """
    subjects = SUBJECT_ALIASES_BY_STATEMENT.get(statement_type, {})
    for std, aliases in subjects.items():
        for alias in aliases:
            alias_c = _clean_text(alias)
            if not alias_c:
                continue
            if alias_c in line_compact:
                return std, alias
    return None


def _scan_page(
    page_text: str,
    page_no: int,
    statement_type: str,
    mult: float,
    active: Optional[str],
    targets: set[str],
) -> Tuple[Dict[str, _FoundValue], Optional[str]]:
    """扫描单页，返回 (命中字典, 更新后的 active 上下文)

    借鉴 workbuddy 的核心扫描逻辑：
    1. 检测本页是否是新报表标题 → 更新 active
    2. 检测母公司报表标题 → 重置 active 为 None
    3. 若 active 与目标不匹配 → 跳过
    4. 逐行扫描，行长度过滤，alias 包含匹配
    5. 行末两个数值：第一个=本年，第二个=上年
    6. 同 key 多次命中保留置信度最高
    7. 跨行拼接：本行无数值拼下一行再试
    """
    new_active = active
    detected = _detect_statement_kind(page_text)
    has_parent = _has_parent_header(page_text)

    # 修复：即使检测到下一报表关键词，只要本页仍含当前报表的已知科目，
    # 就认为本页仍属于当前报表（避免交叉引用导致上下文误切换）
    from app.pdf.page_locator import _KNOWN_SUBJECTS
    known_subjects = _KNOWN_SUBJECTS.get(statement_type, [])
    page_compact = _clean_text(page_text)
    still_in_statement = known_subjects and any(s in page_compact for s in known_subjects)

    if still_in_statement:
        # 本页含当前报表科目 → 强制保持当前报表上下文
        new_active = statement_type
    elif detected:
        new_active = detected
    elif has_parent:
        new_active = None

    # 若本页不在目标报表的上下文里，跳过
    if new_active != statement_type:
        return {}, new_active

    best: Dict[str, _FoundValue] = {}
    lines = page_text.splitlines()
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        # 借鉴策略1：行长度过滤
        compact = _clean_text(line)
        if len(compact) > _MAX_LINE_LEN:
            continue
        # 行内匹配科目
        match = _match_subject_in_line(compact, statement_type)
        if not match:
            continue
        std, alias = match
        # 只补漏 already_found 中不存在的
        if std not in targets:
            continue
        # 取行末两个数值
        current, prior = _choose_two_values(line)
        if current is None:
            # 借鉴策略5：跨行拼接（只跨下一行，避免误拿其它科目数字）
            if idx + 1 < len(lines):
                joined = line + " " + lines[idx + 1].strip()
                current, prior = _choose_two_values(joined)
            if current is None:
                continue
        # 计算置信度
        conf = _CONFIDENCE_SAME_PAGE if detected else _CONFIDENCE_CROSS_PAGE
        if compact.startswith(_clean_text(alias)):
            conf += _CONFIDENCE_LINE_START_BONUS
        conf = min(conf, 0.99)
        fv = _FoundValue(
            standard=std,
            value=current * mult,
            prior_value=(prior * mult) if prior is not None else None,
            page=page_no,
            line=line,
            confidence=conf,
        )
        old = best.get(std)
        if old is None or fv.confidence > old.confidence:
            best[std] = fv
    return best, new_active


# ============================================================
# 主入口
# ============================================================


def fallback_scan(
    pdf_path: str,
    year: int,
    statement_type: str,
    already_found: set[str],
    company_name: str = "",
) -> List[LineItem]:
    """对单份 PDF 做补漏扫描，返回补漏的 LineItem 列表。

    参数：
        pdf_path: PDF 文件路径
        year: 目标年份（用于构造 LineItem）
        statement_type: 报表类型（如"合并资产负债表"）
        already_found: 主解析器已识别的标准科目名集合，不再补这些
        company_name: 公司名（仅用于日志）

    返回：
        补漏的 LineItem 列表（含 prior_year 上年数据时，会用 year-1 单独构造 LineItem）

    借鉴 workbuddy 的 5 大策略：
    1. 行长度过滤
    2. 跨页延续上下文
    3. 双数值策略（current + prior）
    4. 置信度模型
    5. 跨行拼接
    + 必备科目校验（缺失发警告）
    """
    # 待补漏的科目 = 该报表全部标准科目 - 已识别
    all_standard = set(list_standard_subjects(statement_type))
    targets = all_standard - already_found
    if not targets:
        return []

    # 1) 主解析器已找到的页范围（强证据区）
    main_range = locate_statement_pages(pdf_path, statement_type)
    # 2) 扫描所有页（fallback 区，用 active 变量延续上下文）
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[fallback_scan] 打开 PDF 失败: {pdf_path} -> {e}")
        return []

    page_texts: List[Tuple[int, str]] = []
    try:
        total_pages = len(doc)
        # 限制扫描页数避免超大 PDF 慢
        scan_limit = min(total_pages, 200)
        for i in range(scan_limit):
            try:
                page_texts.append((i + 1, doc[i].get_text("text", sort=True) or ""))
            except Exception:
                page_texts.append((i + 1, ""))
    finally:
        try:
            doc.close()
        except Exception:
            pass

    # 扫描所有页
    all_best: Dict[str, _FoundValue] = {}
    active: Optional[str] = None
    # 先扫描主范围（强证据区），再扫描其他页（fallback 区）
    if main_range:
        start, end = main_range
        main_pages = [(p, t) for p, t in page_texts if start <= p <= end]
        fallback_pages = [(p, t) for p, t in page_texts if not (start <= p <= end)]
    else:
        main_pages = []
        fallback_pages = page_texts

    for page_no, text in main_pages + fallback_pages:
        if not text:
            continue
        mult = _detect_unit_multiplier(text)
        page_best, active = _scan_page(text, page_no, statement_type, mult, active, targets)
        for std, fv in page_best.items():
            old = all_best.get(std)
            if old is None or fv.confidence > old.confidence:
                all_best[std] = fv

    # 构造 LineItem
    items: List[LineItem] = []
    # 单位：用主范围首页的单位，否则按元处理
    if main_range:
        unit = detect_unit_for_statement(pdf_path, main_range[0])
    else:
        # 退化：从单位倍率反推
        for _, text in page_texts[:5]:
            mult = _detect_unit_multiplier(text)
            if mult == 1e4:
                unit = "万元"
            elif mult == 1e6:
                unit = "百万元"
            elif mult == 1e3:
                unit = "千元"
            else:
                unit = "元"
            break
        else:
            unit = "元"

    for std, fv in all_best.items():
        # 当前年 LineItem
        items.append(LineItem(
            year=year,
            statement_type=statement_type,
            name=std,
            aliases=[fv.line],
            original_value=fv.value,
            unit=unit,
            source_pdf=pdf_path,
            source_page=fv.page,
            is_recognized=True,
        ))
        # 借鉴策略3：双数值策略的 prior 用上年补漏
        # 只在 prior 非 None 且 already_found 中含此科目时构造 year-1 LineItem
        # （如果 already_found 没有此科目的当前年，上年也没必要补，由后续 PDF 解析时再补）
        if fv.prior_value is not None and std in already_found:
            items.append(LineItem(
                year=year - 1,
                statement_type=statement_type,
                name=std,
                aliases=[fv.line],
                original_value=fv.prior_value,
                unit=unit,
                source_pdf=pdf_path,
                source_page=fv.page,
                is_recognized=True,
            ))

    # 借鉴策略6：必备科目校验
    must = _MUST_HAVE.get(statement_type, [])
    still_missing = [s for s in must if s not in already_found and s not in all_best]
    if still_missing:
        print(f"[fallback_scan] 警告：{statement_type} 必备科目仍缺失: {still_missing}")

    return items
