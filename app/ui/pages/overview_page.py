# -*- coding: utf-8 -*-
"""企业体检总览页 - 展示规则引擎批量执行结果

布局：
- 顶部：公司基本信息
- 中部：年度体检结果表（行=规则，列=年份，值=状态+实际值）
- 底部：体检结论汇总
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QMessageBox,
)

from app.config import format_yuan
from app.models.project import AnalysisProject
from app.models.rule import RuleStatus


# 状态颜色映射
_STATUS_COLORS = {
    RuleStatus.ADVANTAGE: QColor(200, 240, 200),       # 浅绿
    RuleStatus.NORMAL: QColor(220, 240, 255),         # 浅蓝
    RuleStatus.ATTENTION: QColor(255, 240, 200),      # 浅黄
    RuleStatus.HIGH_RISK: QColor(255, 200, 200),      # 浅红
    RuleStatus.ELIMINATE: QColor(255, 180, 180),      # 红
    RuleStatus.NOT_APPLICABLE: QColor(245, 245, 245), # 浅灰
}

_STATUS_TEXT = {
    RuleStatus.ADVANTAGE: "优势",
    RuleStatus.NORMAL: "正常",
    RuleStatus.ATTENTION: "关注",
    RuleStatus.HIGH_RISK: "高风险",
    RuleStatus.ELIMINATE: "淘汰",
    RuleStatus.NOT_APPLICABLE: "—",
}


class OverviewPage(QWidget):
    """企业体检总览页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: AnalysisProject | None = None
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # 标题
        self.title_label = QLabel("企业体检总览")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #333;")
        root.addWidget(self.title_label)

        self.info_label = QLabel("请先导入年报 PDF 并完成数据确认。")
        self.info_label.setStyleSheet("font-size: 14px; color: #666;")
        root.addWidget(self.info_label)

        # 图例
        legend = QLabel(
            "  ■ 优势　■ 正常　■ 关注　■ 高风险　■ 淘汰　■ 暂不适用/未实现"
        )
        legend.setStyleSheet("font-size: 12px; color: #888;")
        root.addWidget(legend)

        # 体检结果表
        self.table = QTableWidget(0, 0)
        self.table.setStyleSheet("font-size: 12px;")
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

        # 底部结论汇总
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(
            "font-size: 13px; color: #444; padding: 8px; "
            "background-color: #f8f8f8; border-radius: 4px;"
        )
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        # 刷新按钮（数据确认页修改后回到此页可重算）
        self.btn_refresh = QPushButton("  重新计算  ")
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #2c7be5; color: white; "
            "font-size: 13px; padding: 6px 18px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1a68d4; }"
        )
        self.btn_refresh.clicked.connect(self._on_refresh)
        root.addWidget(self.btn_refresh)

    # ------------------------------------------------------------------ 加载

    def load_project(self, project: AnalysisProject) -> None:
        """主窗口加载项目时调用"""
        self.project = project
        self._reload()

    def _reload(self) -> None:
        if self.project is None:
            return
        years = self.project.get_years()
        self.info_label.setText(
            f"公司：{self.project.company.display_name()}　|　"
            f"年份：{years[0]}—{years[-1]}（共 {len(years)} 年）　|　"
            f"科目数据：{len(self.project.line_items)} 条　|　"
            f"规则结果：{len(self.project.rule_results)} 条"
        )
        self._build_table()

    # ------------------------------------------------------------------ 表格

    def _build_table(self) -> None:
        """根据 project.rule_results 构建体检表"""
        if self.project is None:
            return
        years = self.project.get_years()
        # 列：规则名 + 各年份 + 课程出处
        n_cols = 1 + len(years) + 1
        self.table.setColumnCount(n_cols)
        headers = ["体检项"] + [str(y) for y in years] + ["课程出处"]
        self.table.setHorizontalHeaderLabels(headers)

        # 按规则 id 分组（保持 rules.json 顺序）
        # 用 dict 保留出现顺序
        rules_dict: dict[str, dict] = {}
        for r in self.project.rule_results:
            if r.rule_id not in rules_dict:
                rules_dict[r.rule_id] = {
                    "rule_name": r.rule_name,
                    "course_source": r.course_source or "",
                    "years": {},
                }
            rules_dict[r.rule_id]["years"][r.year] = r

        self.table.setRowCount(len(rules_dict))
        for row, (rule_id, info) in enumerate(rules_dict.items()):
            # 规则名
            name_item = QTableWidgetItem(info["rule_name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setForeground(QBrush(QColor(50, 50, 50)))
            self.table.setItem(row, 0, name_item)

            # 各年结果
            for ci, yr in enumerate(years):
                col = 1 + ci
                r = info["years"].get(yr)
                if r is None:
                    cell = QTableWidgetItem("—")
                    cell.setBackground(QBrush(_STATUS_COLORS[RuleStatus.NOT_APPLICABLE]))
                else:
                    status = r.status
                    text = _STATUS_TEXT.get(status, "—")
                    if r.actual_value is not None and r.is_calculable:
                        # 实际值显示
                        if "ratio" in rule_id or "margin" in rule_id or "ratio" in rule_id:
                            val_text = f"{r.actual_value:.2%}"
                        else:
                            val_text = format_yuan(r.actual_value)
                        cell = QTableWidgetItem(f"{text}\n{val_text}")
                    else:
                        cell = QTableWidgetItem(f"{text}\n{r.conclusion}")
                    cell.setBackground(QBrush(_STATUS_COLORS.get(status, _STATUS_COLORS[RuleStatus.NOT_APPLICABLE])))
                    cell.setToolTip(r.conclusion)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, cell)

            # 课程出处
            src_item = QTableWidgetItem(info["course_source"])
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            src_item.setForeground(QBrush(QColor(150, 150, 150)))
            self.table.setItem(row, n_cols - 1, src_item)

        # 汇总结论
        self._build_summary()

    def _build_summary(self) -> None:
        """底部汇总：5 年综合体检结论"""
        if self.project is None or not self.project.rule_results:
            self.summary_label.setText("尚无规则结果。")
            return
        # 统计各状态出现次数
        from collections import Counter
        status_count = Counter(r.status for r in self.project.rule_results)
        parts = []
        for st in [RuleStatus.ADVANTAGE, RuleStatus.NORMAL, RuleStatus.ATTENTION,
                   RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE, RuleStatus.NOT_APPLICABLE]:
            n = status_count.get(st, 0)
            if n > 0:
                parts.append(f"{_STATUS_TEXT[st]} {n} 项")
        summary = "　|　".join(parts)
        # 检查是否有淘汰项
        eliminate_count = status_count.get(RuleStatus.ELIMINATE, 0)
        if eliminate_count > 0:
            summary = f"⚠ 检出 {eliminate_count} 项淘汰项，请重点关注。　|　{summary}"
        self.summary_label.setText(summary)

    # ------------------------------------------------------------------ 事件

    def _on_refresh(self) -> None:
        """重新执行规则引擎"""
        if self.project is None:
            return
        from app.rules.engine import apply_all
        apply_all(self.project)
        self._reload()
        QMessageBox.information(self, "已更新", "已根据当前数据重新计算体检结果。")
