# -*- coding: utf-8 -*-
"""
财务真实性检测页 - 检测企业财务数据真实性，识别可能的财务造假风险。

借鉴课程第 19 周"财务造假识别"框架 + rules.json step=0 的 5 条真实性检测规则：
1. 现金利息收益率（auth_cash_interest_yield）：< 2% 提示货币资金异常
2. 预付款项/总资产（auth_prepayment_ratio）：> 3% 提示预付异常
3. (预付+其他应收)/总资产（auth_prepay_other_receivable）：> 10% 高风险
4. 收现比（auth_cash_receipt_ratio）：< 0.80 提示销售造假
5. 净现比（auth_net_profit_cash_ratio）：< 0.80 提示利润造假

布局：
- 顶部：公司信息 + 风险概况
- 中部：5 条规则 × 多个年份的状态矩阵
- 底部：真实性检测结论（综合判定）
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


# 真实性检测只保留文字结果，不再使用背景颜色
# （用户反馈：背景色让结果难以辨识，且容易误认为"全是高风险"）
_STATUS_COLORS = {
    RuleStatus.ADVANTAGE: None,
    RuleStatus.NORMAL: None,
    RuleStatus.ATTENTION: None,
    RuleStatus.HIGH_RISK: None,
    RuleStatus.ELIMINATE: None,
    RuleStatus.NOT_APPLICABLE: None,
}


_STATUS_TEXT = {
    RuleStatus.ADVANTAGE: "正常",
    RuleStatus.NORMAL: "正常",
    RuleStatus.ATTENTION: "关注",
    RuleStatus.HIGH_RISK: "高风险",
    RuleStatus.ELIMINATE: "淘汰",
    RuleStatus.NOT_APPLICABLE: "—",
}


class AuthenticityPage(QWidget):
    """财务真实性检测页"""

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
        self.title_label = QLabel("财务真实性检测")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #333;")
        root.addWidget(self.title_label)

        self.info_label = QLabel("请先导入年报并完成数据确认。")
        self.info_label.setStyleSheet("font-size: 14px; color: #666;")
        root.addWidget(self.info_label)

        # 检测说明
        desc = QLabel(
            "本页通过 5 项关键指标识别可能的财务造假风险：\n"
            "  ① 现金利息收益率 < 2% → 货币资金可能虚构\n"
            "  ② 预付款项/总资产 > 3% → 预付可能异常\n"
            "  ③ (预付+其他应收)/总资产 > 10% → 关联方占用资金高风险\n"
            "  ④ 收现比 < 0.80 → 销售可能造假\n"
            "  ⑤ 净现比 < 0.80 → 净利润可能虚增"
        )
        desc.setStyleSheet("font-size: 12px; color: #555; padding: 8px; "
                          "background-color: #f8f8f8; border-radius: 4px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # 图例
        legend = QLabel("检测结果文字说明：正常 / 关注 / 高风险 / 淘汰 / —（暂不适用或数据缺失）")
        legend.setStyleSheet("font-size: 12px; color: #888;")
        root.addWidget(legend)

        # 检测结果表
        self.table = QTableWidget(0, 0)
        self.table.setStyleSheet("font-size: 12px;")
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

        # 风险概况标签
        self.risk_label = QLabel("")
        self.risk_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 12px; "
            "background-color: #f8f8f8; border-radius: 4px;"
        )
        self.risk_label.setWordWrap(True)
        root.addWidget(self.risk_label)

        # 底部结论
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(
            "font-size: 13px; color: #444; padding: 8px; "
            "background-color: #f8f8f8; border-radius: 4px;"
        )
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        # 刷新按钮
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
            f"规则结果：{len(self.project.rule_results)} 条"
        )
        self._build_table()
        self._build_summary()

    # ------------------------------------------------------------------ 表格

    def _build_table(self) -> None:
        """构建检测结果表：只显示 step=0 的 5 条真实性检测规则"""
        if self.project is None:
            return
        years = self.project.get_years()

        # 真实性检测的 5+3 条规则 ID（按检测维度顺序）
        auth_rule_ids = [
            "auth_cash_interest_yield",
            "auth_prepayment_ratio",
            "auth_prepay_other_receivable",
            "auth_cash_receipt_ratio",
            "auth_net_profit_cash_ratio",
            # 2026-09-16 补齐的 3 个 BS-based 信号
            "auth_cash_interest_debt_combo",
            "auth_fixed_assets_growth",
            "auth_gross_margin_volatility",
        ]

        # 过滤出真实性检测结果
        auth_results: dict[str, dict[int, any]] = {}  # rule_id -> {year -> RuleResult}
        rule_meta: dict[str, str] = {}  # rule_id -> "rule_name\ncourse_source"
        for r in self.project.rule_results:
            if r.rule_id in auth_rule_ids:
                if r.rule_id not in auth_results:
                    auth_results[r.rule_id] = {}
                    rule_meta[r.rule_id] = r.rule_name
                auth_results[r.rule_id][r.year] = r

        # 列：检测项 + 各年份 + 课程出处
        n_cols = 1 + len(years) + 1
        self.table.setColumnCount(n_cols)
        headers = ["检测项"] + [str(y) for y in years] + ["课程出处"]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(auth_rule_ids))

        for row, rid in enumerate(auth_rule_ids):
            # 检测项名
            name_text = rule_meta.get(rid, rid)
            name_item = QTableWidgetItem(name_text)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setForeground(QBrush(QColor(50, 50, 50)))
            self.table.setItem(row, 0, name_item)

            # 各年份结果
            for ci, yr in enumerate(years):
                col = 1 + ci
                r = auth_results.get(rid, {}).get(yr)
                if r is None:
                    cell = QTableWidgetItem("—")
                else:
                    status = r.status
                    status_text = _STATUS_TEXT.get(status, "—")
                    if r.actual_value is not None and r.is_calculable:
                        # ③④⑤ 是比率，① 是比率，② 是比率
                        val_text = f"{r.actual_value:.2%}"
                        cell = QTableWidgetItem(f"{status_text}\n{val_text}")
                    else:
                        cell = QTableWidgetItem(f"{status_text}\n{r.conclusion}")
                    cell.setToolTip(r.conclusion)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, cell)

            # 课程出处
            any_r = next(iter(auth_results.get(rid, {}).values()), None)
            course_src = any_r.course_source if any_r else ""
            src_item = QTableWidgetItem(course_src)
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            src_item.setForeground(QBrush(QColor(150, 150, 150)))
            self.table.setItem(row, n_cols - 1, src_item)

    # ------------------------------------------------------------------ 结论

    def _build_summary(self) -> None:
        """底部综合结论：基于 5 项检测综合判定
        在综合建议中列出真实性存疑的具体科目
        """
        if self.project is None or not self.project.rule_results:
            self.summary_label.setText("尚无检测结果。")
            self.risk_label.setText("")
            return

        auth_rule_ids = {
            "auth_cash_interest_yield", "auth_prepayment_ratio",
            "auth_prepay_other_receivable", "auth_cash_receipt_ratio",
            "auth_net_profit_cash_ratio",
            # 2026-09-16 补齐的 3 个 BS-based 信号
            "auth_cash_interest_debt_combo", "auth_fixed_assets_growth",
            "auth_gross_margin_volatility",
        }
        auth_results = [r for r in self.project.rule_results if r.rule_id in auth_rule_ids]

        from collections import Counter
        status_count = Counter(r.status for r in auth_results)

        # 检测项数 + 高风险/淘汰项数
        total_items = len(auth_results)
        high_risk_count = status_count.get(RuleStatus.HIGH_RISK, 0)
        eliminate_count = status_count.get(RuleStatus.ELIMINATE, 0)
        attention_count = status_count.get(RuleStatus.ATTENTION, 0)
        normal_count = status_count.get(RuleStatus.ADVANTAGE, 0) + \
                       status_count.get(RuleStatus.NORMAL, 0)

        # 综合判定
        if eliminate_count > 0 or high_risk_count >= 2:
            risk_level = "🔴 高风险"
            risk_color = "#dc3545"
            advice = "出现淘汰项或多处高风险，财务数据真实性存疑，强烈不建议投资。"
        elif high_risk_count == 1 or attention_count >= 2:
            risk_level = "🟡 中风险"
            risk_color = "#fd7e14"
            advice = "存在个别异常项，建议进一步结合附注与审计意见核实。"
        elif attention_count == 1:
            risk_level = "🟡 低风险"
            risk_color = "#ffc107"
            advice = "存在 1 项关注项，整体真实性尚可，留意趋势变化。"
        else:
            risk_level = "🟢 低风险"
            risk_color = "#28a745"
            advice = "8 项真实性指标均正常，财务数据真实性较好。"

        # 风险概况
        latest_year = max(r.year for r in auth_results) if auth_results else "—"
        latest_results = [r for r in auth_results if r.year == latest_year]
        latest_high = sum(1 for r in latest_results
                          if r.status in (RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE))
        self.risk_label.setText(
            f"{latest_year} 年真实性检测结果：{risk_level}　|　"
            f"高风险/淘汰 {latest_high} 项 / 共 {len(latest_results)} 项"
        )
        self.risk_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; padding: 12px; "
            f"background-color: {risk_color}22; border-left: 4px solid {risk_color}; "
            f"border-radius: 4px;"
        )

        # 收集真实性存疑项（高风险/淘汰/关注），按最新年份
        suspicious_items = []
        for r in latest_results:
            if r.status in (RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE,
                            RuleStatus.ATTENTION):
                # 取检测项简称（去掉"（真实性检测）"等后缀）
                short_name = r.rule_name.split("（")[0].split("(")[0].strip()
                val_str = f"{r.actual_value:.2%}" if r.actual_value is not None else "—"
                suspicious_items.append(
                    f"  • {short_name}：{val_str}（{_STATUS_TEXT[r.status]}）"
                )

        # 底部总结
        parts = []
        for st in [RuleStatus.ADVANTAGE, RuleStatus.NORMAL, RuleStatus.ATTENTION,
                   RuleStatus.HIGH_RISK, RuleStatus.ELIMINATE, RuleStatus.NOT_APPLICABLE]:
            n = status_count.get(st, 0)
            if n > 0:
                parts.append(f"{_STATUS_TEXT[st]} {n} 项")
        summary = "　|　".join(parts)

        # 综合建议 + 存疑项明细
        suspicious_text = ""
        if suspicious_items:
            suspicious_text = "\n\n真实性存疑项（按严重程度）：\n" + "\n".join(suspicious_items)

        self.summary_label.setText(
            f"全部 {total_items} 项检测结果：{summary}\n"
            f"综合建议：{advice}"
            f"{suspicious_text}"
        )

    # ------------------------------------------------------------------ 事件

    def _on_refresh(self) -> None:
        """重新执行规则引擎"""
        if self.project is None:
            return
        from app.rules.engine import apply_all
        apply_all(self.project)
        self._reload()
        QMessageBox.information(self, "已更新", "已根据当前数据重新计算真实性检测结果。")
