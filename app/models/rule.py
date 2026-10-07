# -*- coding: utf-8 -*-
"""规则与规则结果模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.models.line_item import LineItem


class RuleStatus(Enum):
    """规则结论状态（需求书第 36 节）"""
    ADVANTAGE = "优势"  # 🟢
    NORMAL = "一般"  # ⚪
    ATTENTION = "关注"  # 🟡
    HIGH_RISK = "高风险"  # 🔴
    ELIMINATE = "淘汰"  # 课程中"淘汰"项，UI 上比"高风险"更严重
    NOT_APPLICABLE = "不适用"  # 数据缺失或分母为 0

    def icon(self) -> str:
        return {
            RuleStatus.ADVANTAGE: "🟢",
            RuleStatus.NORMAL: "⚪",
            RuleStatus.ATTENTION: "🟡",
            RuleStatus.HIGH_RISK: "🔴",
            RuleStatus.ELIMINATE: "🔴",
            RuleStatus.NOT_APPLICABLE: "—",
        }[self]


@dataclass
class Rule:
    """一条分析规则（来自 rules.json）"""
    id: str  # 规则 ID，如 "asset_liability_ratio"
    name: str  # 中文名，如"资产负债率"
    step: int  # 18 步中的第几步（0 表示不在 18 步内，如真实性检测）
    formula_ref: str  # 公式标识，对应 formulas.py 的函数名
    thresholds: Dict[str, Any]  # 阈值配置
    conclusion_template: str  # 结论文字模板
    course_source: str  # 课程出处，如"第15周第5页/第19周第3页"
    description: str = ""  # 规则说明
    statement_type: str = ""  # 关联的报表类型


@dataclass
class RuleResult:
    """规则执行结果（按年）"""
    rule_id: str
    rule_name: str
    year: int
    actual_value: Optional[float]  # 实际值（已统一为元或为比率）
    reference_value: str  # 参考值描述，如 ">60% 淘汰；70% 警戒；<40% 无风险"
    status: RuleStatus
    conclusion: str  # 文字结论，如"最近 5 年资产负债率均低于 40%，无偿债风险"
    evidence: List[LineItem] = field(default_factory=list)  # 证据科目列表
    course_source: str = ""
    is_calculable: bool = True  # False 表示数据缺失或分母为 0，无法计算

    def __repr__(self) -> str:
        v = f"{self.actual_value}" if self.actual_value is not None else "N/A"
        return f"<RuleResult {self.rule_id} {self.year} = {v} ({self.status.value})>"
