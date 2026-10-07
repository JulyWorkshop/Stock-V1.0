# -*- coding: utf-8 -*-
"""财务报表类型与年报元数据"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from app.models.company import Company


class StatementType(Enum):
    """三大财务报表类型"""
    BALANCE_SHEET = "合并资产负债表"
    INCOME_STATEMENT = "合并利润表"
    CASH_FLOW_STATEMENT = "合并现金流量表"


@dataclass
class YearReport:
    """一份年度报告 PDF 的元数据"""
    year: int  # 报告年度，如 2023
    pdf_path: str  # PDF 文件绝对路径
    company: Company  # 公司
    is_annual_report: bool = True  # 是否为年度报告（用于校验）
    report_title: str = ""  # 完整标题，如"贵州茅台酒股份有限公司 2023 年年度报告"
    is_scanned: bool = False  # 是否疑似扫描版（提取字符数过少）
    parse_warnings: List[str] = field(default_factory=list)  # 解析时的警告

    def __repr__(self) -> str:
        return f"<YearReport {self.year} {self.company.name}>"


@dataclass
class ImportValidationError:
    """导入校验错误"""
    code: str  # 错误码，如 "NOT_ANNUAL_REPORT"
    message: str  # 中文错误描述
    file: str = ""  # 涉及的 PDF 文件
    year: Optional[int] = None  # 涉及年份
