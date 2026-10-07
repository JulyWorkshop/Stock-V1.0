# -*- coding: utf-8 -*-
"""分析项目（一次完整分析的顶层聚合）"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.models.company import Company
from app.models.line_item import LineItem
from app.models.rule import RuleResult
from app.models.statements import YearReport, StatementType


@dataclass
class AnalysisProject:
    """一次完整的公司分析项目"""
    company: Company
    year_reports: List[YearReport] = field(default_factory=list)
    line_items: List[LineItem] = field(default_factory=list)  # 所有年份所有报表的所有科目
    rule_results: List[RuleResult] = field(default_factory=list)
    rules_version: str = "1.0"

    # ---- 查询辅助 ----

    def get_years(self) -> List[int]:
        """所有出现过的年份，升序"""
        return sorted({li.year for li in self.line_items})

    def get_line_items_by_year(self, year: int, statement_type: Optional[str] = None) -> List[LineItem]:
        """按年（+报表类型）筛选科目"""
        result = [li for li in self.line_items if li.year == year]
        if statement_type:
            result = [li for li in result if li.statement_type == statement_type]
        return result

    def get_line_item(
        self,
        year: int,
        name: str,
        statement_type: Optional[str] = None,
    ) -> Optional[LineItem]:
        """按年+科目名（+报表类型）取单条"""
        for li in self.line_items:
            if li.year != year:
                continue
            if li.name != name:
                continue
            if statement_type and li.statement_type != statement_type:
                continue
            return li
        return None

    def get_value_in_yuan(self, year: int, name: str, statement_type: Optional[str] = None) -> Optional[float]:
        """便捷取值（已转元）"""
        li = self.get_line_item(year, name, statement_type)
        if li is None:
            return None
        return li.value_in_yuan

    def get_safe_value_in_yuan(self, year: int, name: str, statement_type: Optional[str] = None) -> float:
        """便捷取安全值（已转元，未识别按 0 处理）"""
        li = self.get_line_item(year, name, statement_type)
        if li is None:
            return 0.0
        return li.safe_value_in_yuan

    def get_rule_results(self, rule_id: str) -> List[RuleResult]:
        """取某规则所有年份结果"""
        return [r for r in self.rule_results if r.rule_id == rule_id]

    def __repr__(self) -> str:
        years = self.get_years()
        yrs = f"{years[0]}—{years[-1]}" if years else "无年份"
        return f"<AnalysisProject {self.company.name} {yrs} {len(self.line_items)} 项数据>"
