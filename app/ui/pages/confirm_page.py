# -*- coding: utf-8 -*-
"""
数据确认页 - 展示提取的科目数据，允许用户手工修正。

需求书第 17 节："用户必须能够手工修改识别错误的数据。"

布局：
- 顶部：公司名 + 年份范围 + 报表类型选择
- 中部：表格（行=科目名，列=年份，值可编辑）
- 底部：保存修改 + 标记说明

表格特性：
- 未识别科目（is_recognized=False）→ 浅红背景
- 已修正科目（is_modified=True）→ 浅蓝背景
- 来源页码显示在 tooltip 中
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QGroupBox, QMessageBox,
)

from app.models.project import AnalysisProject
from app.models.line_item import LineItem
from app.config import format_yuan


# 未识别 → 浅红背景
_BG_UNRECOGNIZED = QColor(255, 235, 235)
# 已修正 → 浅蓝背景
_BG_MODIFIED = QColor(230, 240, 255)
# 正常 → 白
_BG_NORMAL = QColor(255, 255, 255)


class ConfirmPage(QWidget):
    """数据确认页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: AnalysisProject | None = None
        self._years: list[int] = []
        self._statement_type: str = "合并资产负债表"
        self._current_items: list[LineItem] = []  # 当前表格对应的 line items（按行）
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # 标题
        self.title_label = QLabel("数据确认")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #333;")
        root.addWidget(self.title_label)

        self.info_label = QLabel("请先导入年报 PDF。")
        self.info_label.setStyleSheet("font-size: 14px; color: #666;")
        root.addWidget(self.info_label)

        # 报表类型选择
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("报表类型："))
        self.combo_statement = QComboBox()
        self.combo_statement.addItem("合并资产负债表", "合并资产负债表")
        self.combo_statement.addItem("合并利润表", "合并利润表")
        self.combo_statement.addItem("合并现金流量表", "合并现金流量表")
        self.combo_statement.currentIndexChanged.connect(self._on_statement_changed)
        ctrl_row.addWidget(self.combo_statement)
        ctrl_row.addStretch()

        self.btn_save = QPushButton("  保存修改  ")
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2c7be5; color: white; "
            "font-size: 13px; padding: 6px 18px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1a68d4; }"
            "QPushButton:disabled { background-color: #aaa; }"
        )
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save)
        ctrl_row.addWidget(self.btn_save)
        root.addLayout(ctrl_row)

        # 图例
        legend = QLabel(
            "  ■ 浅红背景 = 未识别（PDF 中未找到该科目数值）　"
            "  ■ 浅蓝背景 = 已修正　"
            "  双击单元格可编辑数值"
        )
        legend.setStyleSheet("font-size: 12px; color: #888;")
        root.addWidget(legend)

        # 数据表格
        self.table = QTableWidget(0, 0)
        self.table.setStyleSheet("font-size: 12px;")
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed
        )
        root.addWidget(self.table, 1)

        # 底部统计
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 12px; color: #888;")
        root.addWidget(self.stats_label)

    # ------------------------------------------------------------------ 加载

    def load_project(self, project: AnalysisProject) -> None:
        """主窗口导入完成后调用"""
        self.project = project
        years = project.get_years()
        self._years = years
        self.info_label.setText(
            f"公司：{project.company.display_name()}　|　"
            f"年份：{years[0]}—{years[-1]}（共 {len(years)} 年）　|　"
            f"科目数据：{len(project.line_items)} 条"
        )
        self.btn_save.setEnabled(True)
        # 默认显示资产负债表
        self._statement_type = "合并资产负债表"
        self.combo_statement.setCurrentIndex(0)
        self._reload_table()

    # ------------------------------------------------------------------ 表格

    def _reload_table(self) -> None:
        """根据当前报表类型重建表格"""
        if self.project is None:
            return

        stmt = self._statement_type
        # 取该报表类型的所有科目
        items = [li for li in self.project.line_items if li.statement_type == stmt]

        # 按科目名分组（同一科目名可能有多年的数据）
        subject_names: list[str] = []
        seen: set[str] = set()
        # 保持 subject_alias.py 中的定义顺序
        from app.pdf.subject_alias import list_standard_subjects
        for std in list_standard_subjects(stmt):
            if std not in seen:
                subject_names.append(std)
                seen.add(std)
        # 补充不在标准列表中的科目
        for li in items:
            if li.name not in seen:
                subject_names.append(li.name)
                seen.add(li.name)

        years = self._years
        # 列：科目名 + 每年一列 + 来源页
        n_cols = 1 + len(years) + 1
        self.table.setColumnCount(n_cols)
        headers = ["科目"] + [str(y) for y in years] + ["来源页"]
        self.table.setHorizontalHeaderLabels(headers)

        self.table.setRowCount(len(subject_names))
        self._current_items = []

        for row, sname in enumerate(subject_names):
            # 科目名
            name_item = QTableWidgetItem(sname)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setForeground(QBrush(QColor(50, 50, 50)))
            self.table.setItem(row, 0, name_item)

            # 找到该科目在各年的 LineItem
            row_items: list[LineItem | None] = []
            for ci, yr in enumerate(years):
                li = self.project.get_line_item(yr, sname, stmt)
                row_items.append(li)
                col = 1 + ci

                if li is None:
                    # project 中没有该 LineItem——显示红色 0.00 作警示（计算时按 0 处理）
                    cell = QTableWidgetItem("0.00")
                    cell.setBackground(QBrush(_BG_UNRECOGNIZED))
                    cell.setForeground(QBrush(QColor(200, 0, 0)))
                    cell.setToolTip("PDF 中未找到此科目，已按 0 显示。双击可输入实际数值，保存时自动创建科目")
                    self.table.setItem(row, col, cell)
                else:
                    v = li.value
                    if v is None:
                        # 未识别——显示红色 0.00 作警示（计算时按 0 处理）
                        cell = QTableWidgetItem("0.00")
                        cell.setBackground(QBrush(_BG_UNRECOGNIZED))
                        cell.setForeground(QBrush(QColor(200, 0, 0)))
                        cell.setToolTip(
                            f"单位：{li.unit}\n"
                            f"来源：{li.source_pdf.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]} 第 {li.source_page} 页\n"
                            "PDF 中未找到此科目数值，已按 0 显示。双击可输入实际数值修正"
                        )
                    else:
                        # 显示原始数值（保留原始单位语境）
                        cell = QTableWidgetItem(f"{v:,.2f}")
                        if li.is_modified:
                            cell.setBackground(QBrush(_BG_MODIFIED))
                        cell.setToolTip(
                            f"单位：{li.unit}\n"
                            f"原始值：{li.original_value}\n"
                            f"来源：{li.source_pdf.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]} 第 {li.source_page} 页"
                        )
                    self.table.setItem(row, col, cell)

            # 来源页（取第一个有数据的）
            src_page = ""
            for li in row_items:
                if li and li.source_page:
                    src_page = str(li.source_page)
                    break
            page_item = QTableWidgetItem(src_page)
            page_item.setFlags(page_item.flags() & ~Qt.ItemIsEditable)
            page_item.setForeground(QBrush(QColor(150, 150, 150)))
            self.table.setItem(row, n_cols - 1, page_item)

            # 记录这一行的 line items（含 None，保持与列的对齐）
            self._current_items.append(row_items)

        # 统计
        total = len(subject_names)
        recognized = sum(1 for row_items in self._current_items if any(li and li.value is not None for li in row_items))
        self.stats_label.setText(
            f"共 {total} 个科目，已识别 {recognized} 个，"
            f"未识别 {total - recognized} 个。双击数值单元格可修正。"
        )

    # ------------------------------------------------------------------ 事件

    def _on_statement_changed(self, idx: int) -> None:
        data = self.combo_statement.itemData(idx)
        if data and data != self._statement_type:
            self._statement_type = data
            self._reload_table()

    def _on_save(self) -> None:
        """保存表格中所有修改过的数值到 project.line_items

        - 已有 LineItem 且有改动 → 更新 modified_value
        - 无 LineItem 但用户输入了数值 → 创建新 LineItem 加入 project.line_items
        """
        if self.project is None:
            return

        modified_count = 0
        created_count = 0
        stmt = self._statement_type
        years = self._years
        # 取该报表的默认单位（从已有 LineItem 取，否则默认元）
        default_unit = "元"
        for li in self.project.line_items:
            if li.statement_type == stmt and li.unit:
                default_unit = li.unit
                break

        for row, row_items in enumerate(self._current_items):
            sname = self.table.item(row, 0).text()
            for ci, li in enumerate(row_items):
                col = 1 + ci
                cell = self.table.item(row, col)
                if cell is None:
                    continue
                text = cell.text().strip()
                # 跳过空、未识别标记、占位"0.00"（背景是 _BG_UNRECOGNIZED 且文本是"0.00"视为占位）
                if not text or text in ("⚠ 未识别", "—"):
                    continue
                # 检测是否是占位 0.00（未识别警示，用户未编辑）
                is_placeholder_zero = (
                    cell.background().color() == _BG_UNRECOGNIZED
                    and text == "0.00"
                )
                if is_placeholder_zero:
                    continue
                try:
                    new_val = float(text.replace(",", "").replace("，", ""))
                except ValueError:
                    continue

                if li is None:
                    # project 中无此 LineItem → 创建新行项目
                    new_li = LineItem(
                        year=years[ci],
                        statement_type=stmt,
                        name=sname,
                        aliases=[],
                        original_value=None,
                        modified_value=new_val,
                        unit=default_unit,
                        source_pdf="",
                        source_page=0,
                        is_recognized=False,
                    )
                    self.project.line_items.append(new_li)
                    row_items[ci] = new_li
                    created_count += 1
                    cell.setBackground(QBrush(_BG_MODIFIED))
                else:
                    old = li.value
                    if old is None or abs(new_val - old) > 1e-6:
                        li.modified_value = new_val
                        modified_count += 1
                        cell.setBackground(QBrush(_BG_MODIFIED))

        msg_parts = []
        if modified_count:
            msg_parts.append(f"更新 {modified_count} 项")
        if created_count:
            msg_parts.append(f"新建 {created_count} 项")
        msg = "、".join(msg_parts) if msg_parts else "未检测到任何修改"
        QMessageBox.information(self, "保存完成", msg + "。")
