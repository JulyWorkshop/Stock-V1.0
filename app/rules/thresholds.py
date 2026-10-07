# -*- coding: utf-8 -*-
"""
rules.json 加载器。

把 rules.json 解析为：
- list[Rule]：22 条规则（每条转为 Rule dataclass）
- dict：subject_groups 字段原样保留（供 formulas.sum_subject_group 使用）

注意：Rule dataclass 没有 reference_text / implemented_phase1 字段。
本模块将 rules.json 中的 `reference_text` 存入 Rule.description，
将 `implemented_phase1` 字段忽略（是否"已实现"由 engine._FORMULA_MAP 判断）。
"""
import json
from pathlib import Path
from typing import List, Tuple

from app.config import RULES_FILE
from app.models.rule import Rule


def load_rules(rules_path: str | Path = None) -> Tuple[List[Rule], dict]:
    """
    加载 rules.json，返回 (规则列表, subject_groups)。
    rules_path 默认 RULES_FILE。
    把每条 dict 转为 Rule dataclass。
    """
    if rules_path is None:
        rules_path = RULES_FILE
    rules_path = Path(rules_path)

    with open(rules_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    subject_groups = data.get("subject_groups", {}) or {}
    rule_dicts = data.get("rules", []) or []

    rules: List[Rule] = []
    for r in rule_dicts:
        # reference_text 字段（参考值描述）放入 Rule.description
        # （Rule dataclass 无 reference_text 字段，复用 description 以保留原文）
        description = r.get("reference_text", "") or r.get("description", "") or ""
        rules.append(
            Rule(
                id=r["id"],
                name=r["name"],
                step=r["step"],
                formula_ref=r["formula_ref"],
                thresholds=r.get("thresholds", {}) or {},
                conclusion_template=r.get("conclusion_template", "") or "",
                course_source=r.get("course_source", "") or "",
                description=description,
                statement_type=r.get("statement_type", "") or "",
            )
        )
    return rules, subject_groups
