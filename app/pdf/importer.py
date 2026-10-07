# -*- coding: utf-8 -*-
"""
导入多份年报 PDF，校验是否同一公司、是否年报、年份完整性等。

接口：
- class ImportResult
- import_pdfs(paths: list[str]) -> ImportResult
- _extract_company_and_year(pdf_path) -> tuple[Company, int, str, bool]
"""
import os
import re
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

from app.config import Unit  # noqa: F401  (保持与项目其他模块单位约定一致)
from app.models.company import Company
from app.models.statements import YearReport, ImportValidationError


# 非年度报告特征（命中即视为非年报）
_NON_ANNUAL_KEYWORDS = [
    "季度报告", "半年度报告", "中期报告", "ESG报告", "社会责任报告",
    "第一季度", "第三季度", "半年报", "季报",
]
# 年报特征（应至少命中一处）
_ANNUAL_KEYWORDS = ["年度报告", "年报"]

# 扫描版判定阈值：每页平均字符数低于此值即视为扫描版
_SCAN_CHAR_THRESHOLD = 200

# 公司名提取用正则
_RE_COMPANY_NAME = re.compile(r"(?:公司中文名称|公司的中文名称|中文名称)\s*[:：]?\s*([^\n\r]{2,80}?股份有限公司[^\n\r]{0,40})")
_RE_COMPANY_NAME_FALLBACK = re.compile(r"([\u4e00-\u9fa5]{2,40}股份有限公司)")
_RE_STOCK_CODE = re.compile(r"(?:股票代码|股票简称代码|证券代码)\s*[:：]?\s*(\d{6})")
_RE_STOCK_CODE_FALLBACK = re.compile(r"(\d{6})")
# 年份提取正则
_RE_YEAR_ANNUAL = re.compile(r"(20\d{2})\s*年\s*年?度?报告")
_RE_YEAR_GENERIC = re.compile(r"(20\d{2})")


class ImportResult:
    """导入结果"""
    def __init__(self):
        self.reports: list[YearReport] = []              # 校验通过的年报
        self.errors: list[ImportValidationError] = []    # 阻断性错误
        self.warnings: list[ImportValidationError] = []  # 警告但可继续

    def __repr__(self) -> str:
        return (
            f"<ImportResult reports={len(self.reports)} "
            f"errors={len(self.errors)} warnings={len(self.warnings)}>"
        )


def _read_first_pages_text(pdf_path: str, num_pages: int = 3) -> tuple[str, int, int]:
    """
    读取 PDF 前 num_pages 页文本及总页数。
    返回 (拼接文本, 总页数, 前 num_pages 页字符数合计)。
    """
    doc = fitz.open(pdf_path)
    try:
        total_pages = len(doc)
        chunks = []
        first_n_chars = 0
        for i in range(min(num_pages, total_pages)):
            text = doc[i].get_text("text") or ""
            chunks.append(text)
            first_n_chars += len(text)
        # 同时统计全文档字符数（用于扫描版判定）
        all_chars = 0
        for i in range(total_pages):
            try:
                all_chars += len(doc[i].get_text("text") or "")
            except Exception:
                pass
        return "".join(chunks), total_pages, all_chars
    finally:
        try:
            doc.close()
        except Exception:
            pass


def _extract_company_and_year(pdf_path: str) -> tuple[Company, int, str, bool]:
    """
    从单份 PDF 提取公司、年份、报告标题、是否年报。
    返回 (company, year, title, is_annual)。提取失败时 year=0, is_annual=False。
    """
    company = Company(name="", stock_code="")
    year = 0
    title = ""
    is_annual = False

    try:
        head_text, total_pages, _ = _read_first_pages_text(pdf_path, num_pages=3)
    except Exception as e:
        print(f"[importer] 读取 PDF 失败: {pdf_path} -> {e}")
        return company, year, title, is_annual

    if not head_text:
        return company, year, title, is_annual

    # --- 提取公司名 ---
    m = _RE_COMPANY_NAME.search(head_text)
    if m:
        raw_name = m.group(1).strip()
    else:
        m = _RE_COMPANY_NAME_FALLBACK.search(head_text)
        raw_name = m.group(1).strip() if m else ""
    # 去掉可能的尾部空白/全角空格
    if raw_name:
        raw_name = raw_name.replace("\u3000", "").strip()
    company.name = raw_name

    # --- 提取股票代码 ---
    m = _RE_STOCK_CODE.search(head_text)
    if m:
        company.stock_code = m.group(1).strip()

    # --- 是否年报 ---
    has_annual_kw = any(kw in head_text for kw in _ANNUAL_KEYWORDS)
    has_non_annual_kw = any(kw in head_text for kw in _NON_ANNUAL_KEYWORDS)
    # 优先非年报关键词（防止年报中提到"季度报告"等字样误判）
    if has_non_annual_kw and not _RE_YEAR_ANNUAL.search(head_text):
        is_annual = False
    else:
        is_annual = has_annual_kw

    # --- 提取年份 ---
    m = _RE_YEAR_ANNUAL.search(head_text)
    if m:
        year = int(m.group(1))
    else:
        m = _RE_YEAR_GENERIC.search(head_text)
        if m:
            year = int(m.group(1))

    # --- 提取标题（尝试取封面首行非空文本）---
    for line in head_text.splitlines():
        line = line.strip()
        if len(line) >= 4 and ("年报" in line or "年度报告" in line or "股份有限公司" in line):
            title = line[:120]
            break
    if not title:
        title = os.path.basename(pdf_path)

    return company, year, title, is_annual


def _is_scanned_pdf(pdf_path: str, total_chars: int, total_pages: int) -> bool:
    """
    简易扫描版判定：每页平均字符数 < 阈值即视为扫描版。
    """
    if total_pages <= 0:
        return False
    avg = total_chars / total_pages
    return avg < _SCAN_CHAR_THRESHOLD


def import_pdfs(paths: list[str]) -> ImportResult:
    """
    导入多份 PDF。校验：
    1. 每份文件可读（fitz.open 不报错）
    2. 是否疑似扫描版
    3. 提取公司名+股票代码
    4. 同一公司
    5. 是否年度报告
    6. 提取年份
    7. 排序：按 year 升序
    8. 缺失年份（连续性）
    9. 重复年份
    """
    result = ImportResult()

    if not paths:
        return result

    # 1) 逐份解析单文件
    parsed: list[tuple[str, Company, int, str, bool, bool]] = []  # (path, company, year, title, is_annual, is_scanned)
    for path in paths:
        # 1. 可读性
        if not path or not os.path.isfile(path):
            result.errors.append(ImportValidationError(
                code="FILE_NOT_FOUND",
                message=f"文件不存在或不可读: {path}",
                file=path,
            ))
            continue
        try:
            doc = fitz.open(path)
            total_pages = len(doc)
            total_chars = 0
            for i in range(total_pages):
                try:
                    total_chars += len(doc[i].get_text("text") or "")
                except Exception:
                    pass
            doc.close()
        except Exception as e:
            result.errors.append(ImportValidationError(
                code="PDF_READ_ERROR",
                message=f"打开 PDF 失败: {e}",
                file=path,
            ))
            continue

        # 2. 扫描版判定
        is_scanned = _is_scanned_pdf(path, total_chars, total_pages)

        # 3/5/6. 公司、年份、是否年报
        company, year, title, is_annual = _extract_company_and_year(path)

        if is_scanned:
            result.warnings.append(ImportValidationError(
                code="POSSIBLE_SCANNED",
                message="可能为扫描版，文本提取字符数过少",
                file=path,
                year=year or None,
            ))

        parsed.append((path, company, year, title, is_annual, is_scanned))

    # 4. 同一公司校验
    valid_companies = [c for (_, c, _, _, _, _) in parsed if c.name or c.stock_code]
    if valid_companies:
        first = valid_companies[0]
        for c in valid_companies[1:]:
            if c != first:
                result.errors.append(ImportValidationError(
                    code="NOT_SAME_COMPANY",
                    message=(
                        f"公司不一致：{first.display_name()} vs {c.display_name()}"
                    ),
                    file="",
                ))
                break  # 一次告警即可

    # 5. 是否年报校验
    for (path, company, year, title, is_annual, is_scanned) in parsed:
        if not is_annual:
            result.errors.append(ImportValidationError(
                code="NOT_ANNUAL_REPORT",
                message="该 PDF 不是年度报告（疑似季报/半年报/ESG 等）",
                file=path,
                year=year or None,
            ))

    # 6. 年份校验：年份为 0 视为提取失败
    for (path, company, year, title, is_annual, is_scanned) in parsed:
        if year == 0:
            result.errors.append(ImportValidationError(
                code="YEAR_NOT_FOUND",
                message="无法从 PDF 提取报告年份",
                file=path,
            ))

    # 7. 重复年份
    year_to_paths: dict[int, list[str]] = {}
    for (path, company, year, title, is_annual, is_scanned) in parsed:
        if year <= 0:
            continue
        year_to_paths.setdefault(year, []).append(path)
    for y, plist in year_to_paths.items():
        if len(plist) > 1:
            result.errors.append(ImportValidationError(
                code="DUPLICATE_YEAR",
                message=f"{y} 年存在 {len(plist)} 份 PDF",
                file=plist[0],
                year=y,
            ))

    # 把通过基础校验的（非年报/年份失败/重复年份之外）作为 YearReport 加入 reports
    duplicate_years = {y for y, plist in year_to_paths.items() if len(plist) > 1}
    for (path, company, year, title, is_annual, is_scanned) in parsed:
        if year <= 0 or not is_annual:
            continue
        if year in duplicate_years:
            # 重复年份全部不进 reports，已在 errors 提示
            continue
        # 同一公司校验失败也不进
        if valid_companies:
            first = valid_companies[0]
            if company != first:
                continue
        warnings_list: list[str] = []
        if is_scanned:
            warnings_list.append("可能为扫描版")
        report = YearReport(
            year=year,
            pdf_path=os.path.abspath(path),
            company=company,
            is_annual_report=is_annual,
            report_title=title,
            is_scanned=is_scanned,
            parse_warnings=warnings_list,
        )
        result.reports.append(report)

    # 8. 排序：按 year 升序
    result.reports.sort(key=lambda r: r.year)

    # 9. 缺失年份检测：连续性
    if len(result.reports) >= 2:
        years = [r.year for r in result.reports]
        for i in range(years[0], years[-1]):
            if i not in years:
                result.warnings.append(ImportValidationError(
                    code="MISSING_YEAR",
                    message=f"缺失 {i} 年的年报",
                    year=i,
                ))

    return result
