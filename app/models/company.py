# -*- coding: utf-8 -*-
"""公司与年报基础模型"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Company:
    """上市公司"""
    name: str  # 公司全称，如"贵州茅台酒股份有限公司"
    stock_code: str = ""  # 6 位股票代码，如"600519"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Company):
            return False
        # 股票代码优先；代码为空时按名称
        if self.stock_code and other.stock_code:
            return self.stock_code == other.stock_code
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.stock_code or self.name)

    def display_name(self) -> str:
        """UI 展示名"""
        if self.stock_code:
            return f"{self.stock_code} {self.name}"
        return self.name
