# -*- coding: utf-8 -*-
"""
18 步详细分析页 - 按课程 18 步框架逐年/逐项展示规则结果。

布局：
- 顶部：公司信息 + 课程框架说明
- 滚动区域：按 step（1~18）分组的 GroupBox，每步含：
    * 步骤标题 + 课程出处
    * 阈值说明
    * 各年份结果表（年份、实际值、状态、结论）
- 底部：18 步综合判定

规则来源：rules.json 中 step=1~18 的 17 条规则（不含 step=0 真实性检测）
（注：step=1/2 暂未在 rules.json 中定义，但其他 17 步均覆盖）
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QMessageBox, QScrollArea, QVBoxLayout,
)

from app.config import format_yuan
from app.models.project import AnalysisProject
from app.models.rule import RuleStatus


# 状态颜色
_STATUS_COLORS = {
    RuleStatus.ADVANTAGE: QColor(200, 240, 200),
    RuleStatus.NORMAL: QColor(220, 240, 255),
    RuleStatus.ATTENTION: QColor(255, 240, 200),
    RuleStatus.HIGH_RISK: QColor(255, 200, 200),
    RuleStatus.ELIMINATE: QColor(255, 180, 180),
    RuleStatus.NOT_APPLICABLE: QColor(245, 245, 245),
}

_STATUS_TEXT = {
    RuleStatus.ADVANTAGE: "优势",
    RuleStatus.NORMAL: "正常",
    RuleStatus.ATTENTION: "关注",
    RuleStatus.HIGH_RISK: "高风险",
    RuleStatus.ELIMINATE: "淘汰",
    RuleStatus.NOT_APPLICABLE: "—",
}

# 18 步框架标题（按课程第 19 周梳理）
_STEPS_FRAMEWORK = {
    1: ("行业地位与公司基本面", "第19周"),
    2: ("管理层与股权结构", "第19周"),
    3: ("总资产规模与成长性", "第19周第2页（第一节第3步）"),
    4: ("偿债风险分析", "第15周第5页（第十二节）/第19周第3页（第二节第4步）"),
    5: ("竞争优势（应付预收-应收预付）", "第15周第8页（第十三节）/第19周第6页（第三节第5步）"),
    6: ("应收/合同资产占比", "第15周第8页/第19周第6页"),
    7: ("固定资产占比（重资产/轻资产）", "第15周第12页（第十五节）"),
    8: ("投资类资产占比（主业专注度）", "第15周第14页（第十六节）"),
    9: ("存货商誉爆雷风险", "第15周第16页（第十七节）"),
    10: ("营收增长率", "第15周第18页（第十八节）"),
    11: ("毛利率（核心竞争力）", "第15周第20页（第十九节）"),
    12: ("期间费用率/毛利率", "第15周第22页（第二十节）"),
    13: ("销售费用率", "第15周第22页/第19周"),
    14: ("主营利润率", "第15周第24页（第二十一节）"),
    15: ("5 年平均净现比（造血能力）", "第15周第26页（第二十二节）"),
    16: ("ROE（净资产收益率）", "第15周第28页（第二十三节）"),
    17: ("资本开支/经营现金流（扩张能力）", "第15周第30页（第二十四节）"),
    18: ("分红/经营现金流（分红意愿）", "第15周第32页（第二十五节）"),
}


class Steps18Page(QWidget):
    """18 步详细分析页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: AnalysisProject | None = None
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        # 标题
        self.title_label = QLabel("18 步详细分析")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #333;")
        outer.addWidget(self.title_label)

        self.info_label = QLabel("请先导入年报并完成数据确认。")
        self.info_label.setStyleSheet("font-size: 14px; color: #666;")
        outer.addWidget(self.info_label)

        # 框架说明
        desc = QLabel(
            "本页按课程 18 步企业分析框架逐项展示，每步含：实际值、状态、阈值、课程出处、结论文字。\n"
            "  🟢 优势　⚪ 正常　🟡 关注　🔴 高风险/淘汰　— 暂不适用/数据缺失"
        )
        desc.setStyleSheet("font-size: 12px; color: #555; padding: 8px; "
                          "background-color: #f8f8f8; border-radius: 4px;")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        # 滚动容器：放各步骤 GroupBox
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")
        self.scroll_content = QWidget()
        self.steps_layout = QVBoxLayout(self.scroll_content)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(12)
        self.scroll.setWidget(self.scroll_content)
        outer.addWidget(self.scroll, 1)

        # 底部综合结论
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(
            "font-size: 13px; color: #444; padding: 8px; "
            "background-color: #f8f8f8; border-radius: 4px;"
        )
        self.summary_label.setWordWrap(True)
        outer.addWidget(self.summary_label)

        # 重新计算按钮
        self.btn_refresh = QPushButton("  重新计算  ")
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #2c7be5; color: white; "
            "font-size: 13px; padding: 6px 18px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1a68d4; }"
        )
        self.btn_refresh.clicked.connect(self._on_refresh)
        outer.addWidget(self.btn_refresh)

    # ------------------------------------------------------------------ 加载

    def load_project(self, project: AnalysisProject) -> None:
        self.project = project
        self._reload()

    def _reload(self) -> None:
        if self.project is None:
            return
        years = self.project.get_years()
        self.info_label.setText(
            f"公司：{self.project.company.display_name()}　|　"
            f"年份：{years[0]}—{years[-1]}（共 {len(years)} 年）　|　"
            f"规则结果：{len(self.project.rule_results)} 条"
        )
        self._build_steps()
        self._build_summary()

    # ------------------------------------------------------------------ 步骤构建

    def _build_steps(self) -> None:
        """按 18 步分组构建 GroupBox"""
        # 清空旧的
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self.project is None:
            return

        years = self.project.get_years()

        # 按 step 分组规则结果
        # step_results: dict[int, list[RuleResult]]
        from collections import defaultdict
        step_results = defaultdict(list)
        for r in self.project.rule_results:
            # 找规则的 step
            step = self._get_step_for_rule(r.rule_id)
            if step > 0:
                step_results[step].append(r)

        # 找每个 step 对应的 rule_id（用于查询阈值和课程出处）
        # 从 rules.json 加载
        from app.rules.thresholds import load_rules
        all_rules, _ = load_rules()
        rule_by_id = {r.id: r for r in all_rules}

        for step_no in range(1, 19):
            title, course_src = _STEPS_FRAMEWORK.get(step_no, (f"第 {step_no} 步", ""))
            results = step_results.get(step_no, [])

            # 构建步骤 GroupBox
            if results:
                # 取第一条结果的 rule_name
                rule_name = results[0].rule_name
                # 取规则的阈值描述
                rule_meta = rule_by_id.get(results[0].rule_id)
                thresholds_desc = rule_meta.description if rule_meta else ""
                conclusion_template = rule_meta.conclusion_template if rule_meta else ""
            else:
                rule_name = "（暂未实现）"
                thresholds_desc = ""
                conclusion_template = ""

            gb = QGroupBox(f"第 {step_no} 步：{title}  —  {rule_name}")
            gb_layout = QVBoxLayout(gb)
            gb_layout.setSpacing(6)

            # 步骤元信息行
            meta_label = QLabel(
                f"<b>课程出处：</b>{course_src}<br>"
                + (f"<b>参考阈值：</b>{thresholds_desc}" if thresholds_desc else "")
            )
            meta_label.setStyleSheet("font-size: 12px; color: #555; padding: 4px 6px;")
            meta_label.setWordWrap(True)
            gb_layout.addWidget(meta_label)

            if not results:
                hint = QLabel("此步尚未实现或本年数据缺失")
                hint.setStyleSheet("font-size: 12px; color: #999; padding: 4px 6px;")
                gb_layout.addWidget(hint)
            else:
                # 表格：年份 | 实际值 | 状态 | 结论
                tbl = QTableWidget(len(results), 4)
                tbl.setStyleSheet("font-size: 12px;")
                tbl.setHorizontalHeaderLabels(["年份", "实际值", "状态", "结论"])
                tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
                tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
                tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
                tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
                tbl.setEditTriggers(QTableWidget.NoEditTriggers)
                tbl.verticalHeader().setVisible(False)
                tbl.setFixedHeight(max(28 * len(results) + 28, 60))

                for ri, r in enumerate(sorted(results, key=lambda x: x.year)):
                    # 年份
                    y_item = QTableWidgetItem(str(r.year))
                    y_item.setFlags(y_item.flags() & ~Qt.ItemIsEditable)
                    tbl.setItem(ri, 0, y_item)
                    # 实际值
                    if r.actual_value is not None and r.is_calculable:
                        # 比率 vs 元
                        if isinstance(r.actual_value, dict):
                            # 存货商誉爆雷风险返回 dict
                            val_text = " / ".join(
                                f"{k}={v:.2%}" if isinstance(v, (int, float)) else f"{k}={v}"
                                for k, v in r.actual_value.items()
                                if k != "total_assets"
                            )
                        elif "ratio" in r.rule_id or "margin" in r.rule_id or \
                             "roe" in r.rule_id or "growth" in r.rule_id or \
                             "yield" in r.rule_id or r.rule_id.endswith("_cash_ratio"):
                            val_text = f"{r.actual_value:.2%}"
                        else:
                            val_text = format_yuan(r.actual_value)
                    else:
                        val_text = "—"
                    v_item = QTableWidgetItem(val_text)
                    v_item.setFlags(v_item.flags() & ~Qt.ItemIsEditable)
                    v_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    tbl.setItem(ri, 1, v_item)
                    # 状态
                    s_text = _STATUS_TEXT.get(r.status, "—")
                    s_item = QTableWidgetItem(s_text)
                    s_item.setBackground(QBrush(_STATUS_COLORS.get(r.status,
                                          _STATUS_COLORS[RuleStatus.NOT_APPLICABLE])))
                    s_item.setFlags(s_item.flags() & ~Qt.ItemIsEditable)
                    s_item.setTextAlignment(Qt.AlignCenter)
                    tbl.setItem(ri, 2, s_item)
                    # 结论
                    c_item = QTableWidgetItem(r.conclusion or "")
                    c_item.setFlags(c_item.flags() & ~Qt.ItemIsEditable)
                    c_item.setToolTip(r.conclusion or "")
                    tbl.setItem(ri, 3, c_item)

                gb_layout.addWidget(tbl)

            self.steps_layout.addWidget(gb)

        self.steps_layout.addStretch()

    def _get_step_for_rule(self, rule_id: str) -> int:
        """根据 rule_id 找对应的 step 号"""
        from app.rules.thresholds import load_rules
        all_rules, _ = load_rules()
        for r in all_rules:
            if r.id == rule_id:
                return r.step
        return 0

    # ------------------------------------------------------------------ 总结

    def _build_summary(self) -> None:
        if self.project is None or not self.project.rule_results:
            self.summary_label.setText("尚无规则结果。")
            return

        # 只统计 step > 0 的规则
        from collections import Counter, defaultdict
        step_results = defaultdict(list)
        for r in self.project.rule_results:
            step = self._get_step_for_rule(r.rule_id)
            if step > 0:
                step_results[step].append(r)

        # 统计每个 step 的状态（取最新年）
        latest_year = max(r.year for r in self.project.rule_results)
        step_status = {}
        for step, results in step_results.items():
            latest_results = [r for r in results if r.year == latest_year]
            if latest_results:
                step_status[step] = latest_results[0].status

        # 总览：优势/正常/关注/高风险/淘汰/不适用 步数
        status_count = Counter(step_status.values())
        parts = []
        for st in [RuleStatus.ADVANTAGE, RuleStatus.NORMAL, RuleStatus.ATTENTION,
                   RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE, RuleStatus.NOT_APPLICABLE]:
            n = status_count.get(st, 0)
            if n > 0:
                parts.append(f"{_STATUS_TEXT[st]} {n} 步")
        summary = "　|　".join(parts)

        # 淘汰项警告
        eliminate_count = status_count.get(RuleStatus.ELIMINATE, 0)
        if eliminate_count > 0:
            summary = f"⚠ {latest_year} 年检出 {eliminate_count} 步淘汰项，请重点关注。　|　{summary}"

        self.summary_label.setText(
            f"18 步分析汇总（{latest_year} 年最新状态）：{summary}\n"
            f"共覆盖 {len(step_status)} 步 / 共 18 步框架"
        )

    # ------------------------------------------------------------------ 事件

    def _on_refresh(self) -> None:
        if self.project is None:
            return
        from app.rules.engine import apply_all
        apply_all(self.project)
        self._reload()
        QMessageBox.information(self, "已更新", "已根据当前数据重新计算 18 步分析结果。")
