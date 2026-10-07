# -*- coding: utf-8 -*-
"""财务科目（行项目）模型 - 含来源页码、人工修正"""
from dataclasses import dataclass, field
from typing import List, Optional

from app.config import unit_to_yuan


@dataclass
class LineItem:
    """一个年度某一报表中的一个科目（一行数据）"""
    # 标识
    year: int  # 报告年度
    statement_type: str  # StatementType.value，如 "合并资产负债表"
    name: str  # 标准科目名（已归一），如 "货币资金"
    aliases: List[str] = field(default_factory=list)  # PDF 原文中识别到的别名

    # 数值与单位
    original_value: Optional[float] = None  # PDF 原始识别值
    modified_value: Optional[float] = None  # 用户修正值
    unit: str = "元"  # 该科目的原始单位（元/千元/万元/百万元）

    # 来源追溯（需求书第 41 节）
    source_pdf: str = ""  # 来源 PDF 路径
    source_page: int = 0  # 来源页码（1-based）

    # 标记
    is_recognized: bool = True  # False 表示未识别（PDF 中找不到），需求书第 49 节要求不猜

    @property
    def value(self) -> Optional[float]:
        """当前生效值：修正值优先，否则原始值"""
        if self.modified_value is not None:
            return self.modified_value
        return self.original_value

    @property
    def is_modified(self) -> bool:
        """是否被人工修正过"""
        return (self.modified_value is not None
                and self.original_value is not None
                and abs(self.modified_value - self.original_value) > 1e-6)

    @property
    def value_in_yuan(self) -> Optional[float]:
        """返回以元为单位的当前生效值"""
        v = self.value
        if v is None:
            return None
        return unit_to_yuan(v, self.unit)

    @property
    def safe_value(self) -> float:
        """安全值：未识别（value is None）按 0.0 处理，便于后续公式计算"""
        v = self.value
        return v if v is not None else 0.0

    @property
    def safe_value_in_yuan(self) -> float:
        """以元为单位的安全值：未识别按 0.0 处理"""
        return unit_to_yuan(self.safe_value, self.unit)

    def __repr__(self) -> str:
        v = self.value
        v_str = f"{v}" if v is not None else "⚠ 未识别"
        mod = " (已修正)" if self.is_modified else ""
        return f"<LineItem {self.year} {self.name}={v_str}{mod} p{self.source_page}>"
