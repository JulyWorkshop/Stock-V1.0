# -*- coding: utf-8 -*-
"""应用配置常量与路径"""
import os
import sys
from pathlib import Path

# 应用信息
APP_NAME = "股票价值投资财报分析软件"
APP_VERSION = "1.0"
RULES_VERSION = "1.0"

# 路径处理：兼容 PyInstaller 打包
# 打包后 sys.frozen=True，资源文件在 sys._MEIPASS（临时解压目录）
_IS_FROZEN = getattr(sys, "frozen", False)

if _IS_FROZEN:
    # 打包模式：资源文件被提取到临时目录
    BUNDLE_DIR = Path(sys._MEIPASS)
    RULES_FILE = BUNDLE_DIR / "rules.json"
    SCHEMA_FILE = BUNDLE_DIR / "app" / "data" / "schema.sql"
    DATA_DIR = BUNDLE_DIR / "app" / "data"
    APP_DIR = Path(sys.executable).resolve().parent
    PROJECT_ROOT = APP_DIR
else:
    # 开发模式
    APP_DIR = Path(__file__).resolve().parent.parent  # ffa/
    PROJECT_ROOT = APP_DIR.parent  # 工作目录
    RULES_FILE = APP_DIR / "rules.json"
    DATA_DIR = APP_DIR / "app" / "data"
    SCHEMA_FILE = DATA_DIR / "schema.sql"

# 测试
TESTS_DIR = APP_DIR / "tests"


class Unit:
    """年报中可能出现的金额单位枚举"""

    YUAN = "元"
    THOUSAND_YUAN = "千元"
    TEN_THOUSAND_YUAN = "万元"
    MILLION_YUAN = "百万元"
    HUNDRED_MILLION_YUAN = "亿元"

    ALL = [YUAN, THOUSAND_YUAN, TEN_THOUSAND_YUAN, MILLION_YUAN, HUNDRED_MILLION_YUAN]

    # 转换为"元"的倍数
    TO_YUAN_MULTIPLIER = {
        YUAN: 1,
        THOUSAND_YUAN: 1_000,
        TEN_THOUSAND_YUAN: 10_000,
        MILLION_YUAN: 1_000_000,
        HUNDRED_MILLION_YUAN: 100_000_000,
    }


def unit_to_yuan(value: float, unit: str) -> float:
    """将某单位的数值转换为元"""
    multiplier = Unit.TO_YUAN_MULTIPLIER.get(unit, 1)
    return value * multiplier


def format_yuan(value: float) -> str:
    """格式化元为可读字符串（亿元/万元）"""
    if value is None:
        return "—"
    if value == 0:
        return "0"
    abs_val = abs(value)
    if abs_val >= 1e8:
        return f"{value / 1e8:.2f} 亿"
    if abs_val >= 1e4:
        return f"{value / 1e4:.2f} 万"
    return f"{value:.2f}"


def format_percent(value: float, digits: int = 2) -> str:
    """格式化为百分比"""
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"
