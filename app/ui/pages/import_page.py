# -*- coding: utf-8 -*-
"""
导入年报 PDF 页面。

流程：
1. 用户选择多份 PDF（QFileDialog）
2. 点"开始导入" → 启动 ImportWorker 后台线程
3. 后台：import_pdfs(paths) 校验 → 三大表解析 + fallback_scan 补漏
4. 通过 Signal 把进度回传主线程，进度条实时更新，避免 UI 卡顿
5. 完成或错误时通过 Signal 通知主线程，主线程组装 AnalysisProject
"""
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar,
)

from app.config import APP_NAME
from app.models.project import AnalysisProject
from app.models.company import Company
from app.models.statements import StatementType
from app.pdf.importer import import_pdfs
from app.pdf.parsers.balance_sheet import parse_balance_sheet
from app.pdf.parsers.income_statement import parse_income_statement
from app.pdf.parsers.cash_flow import parse_cash_flow
from app.pdf.parsers.fallback_scan import fallback_scan
from app.pdf.parsers.table_parser import parse_statement_by_table


class ImportWorker(QThread):
    """PDF 导入工作线程。

    通过 Signal 回报进度，避免主线程阻塞。
    - progress(percent, stage_text)：进度更新
    - done(result_or_project_or_exception)：完成或异常
      - 校验有错误/无年报：发射 ImportResult（含 errors/warnings）
      - 正常完成：发射 AnalysisProject
      - 异常：发射 Exception 对象
    """
    progress = Signal(int, str)
    done = Signal(object)

    def __init__(self, pdf_paths: list[str]):
        super().__init__()
        self._pdf_paths = list(pdf_paths)

    def run(self) -> None:
        try:
            # 1) 校验（5%）
            self.progress.emit(5, "正在校验 PDF（公司名/年份/年报/扫描版...）")
            result = import_pdfs(self._pdf_paths)

            # 校验失败：直接返回 ImportResult，主线程展示错误
            if result.errors or not result.reports:
                self.progress.emit(100, "校验完成（含错误或无有效年报）")
                self.done.emit(result)
                return

            # 2) 逐份解析三大报表 + fallback_scan 补漏（10%-90%）
            # 策略：优先用表格结构化解析器（find_tables），文本流解析器作为回退补充
            company = result.reports[0].company
            all_items = []
            n = len(result.reports)
            for i, rpt in enumerate(result.reports):
                # 起始进度：10 + (i/n)*80
                pct_start = 10 + int(80 * i / n)
                pct_end = 10 + int(80 * (i + 1) / n)

                # === 资产负债表 ===
                self.progress.emit(pct_start, f"解析 {rpt.year} 年报 ({i+1}/{n})：资产负债表")
                # 先用表格解析器
                bs_items = parse_statement_by_table(rpt.pdf_path, rpt.year, "合并资产负债表", company.name)
                # 如果表格解析器识别率低，用文本流解析器补充
                bs_rec_count = sum(1 for it in bs_items if it.is_recognized)
                if bs_rec_count < 20:  # 表格解析失败，回退到文本流
                    bs_items = parse_balance_sheet(rpt.pdf_path, rpt.year, company.name)
                all_items.extend(bs_items)

                # === 利润表 ===
                self.progress.emit(pct_start + (pct_end - pct_start) // 4,
                                   f"解析 {rpt.year} 年报 ({i+1}/{n})：利润表")
                ic_items = parse_statement_by_table(rpt.pdf_path, rpt.year, "合并利润表", company.name)
                ic_rec_count = sum(1 for it in ic_items if it.is_recognized)
                if ic_rec_count < 10:  # 表格解析失败，回退到文本流
                    ic_items = parse_income_statement(rpt.pdf_path, rpt.year, company.name)
                all_items.extend(ic_items)

                # === 现金流量表 ===
                self.progress.emit(pct_start + (pct_end - pct_start) // 2,
                                   f"解析 {rpt.year} 年报 ({i+1}/{n})：现金流量表")
                cf_items = parse_statement_by_table(rpt.pdf_path, rpt.year, "合并现金流量表", company.name)
                cf_rec_count = sum(1 for it in cf_items if it.is_recognized)
                if cf_rec_count < 10:  # 表格解析失败，回退到文本流
                    cf_items = parse_cash_flow(rpt.pdf_path, rpt.year, company.name)
                all_items.extend(cf_items)

                # === fallback_scan 补漏 ===
                self.progress.emit(pct_end - 1,
                                   f"补漏识别 {rpt.year} 年报 ({i+1}/{n})：扫描其他页面")
                bs_found = {it.name for it in bs_items if it.is_recognized}
                ic_found = {it.name for it in ic_items if it.is_recognized}
                cf_found = {it.name for it in cf_items if it.is_recognized}
                all_items.extend(fallback_scan(rpt.pdf_path, rpt.year, "合并资产负债表", bs_found, company.name))
                all_items.extend(fallback_scan(rpt.pdf_path, rpt.year, "合并利润表", ic_found, company.name))
                all_items.extend(fallback_scan(rpt.pdf_path, rpt.year, "合并现金流量表", cf_found, company.name))

            # 3) 组装项目（95%）
            self.progress.emit(95, "正在组装分析项目...")
            project = AnalysisProject(
                company=company,
                year_reports=list(result.reports),
                line_items=all_items,
            )
            self.progress.emit(100, f"导入完成：{len(result.reports)} 份年报")
            self.done.emit(project)
        except Exception as e:
            self.done.emit(e)


class ImportPage(QWidget):
    """导入年报 PDF 页"""

    # 导入完成时发出，主窗口接收后切换到确认页
    project_ready = Signal(AnalysisProject)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf_paths: list[str] = []
        self._worker: ImportWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # 标题
        title = QLabel("导入年报")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #333;")
        root.addWidget(title)

        desc = QLabel(
            "选择同一家上市公司连续多年的年度报告 PDF（建议 5—10 年）。\n"
            "软件将自动校验是否同一公司、是否年报、年份完整性，并提取资产负债表数据。"
        )
        desc.setStyleSheet("font-size: 13px; color: #666; line-height: 1.6;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("  添加年报 PDF  ")
        self.btn_add.setStyleSheet(
            "QPushButton { background-color: #2c7be5; color: white; "
            "font-size: 14px; padding: 8px 20px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1a68d4; }"
        )
        self.btn_add.clicked.connect(self._on_add_pdfs)

        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.setStyleSheet(
            "QPushButton { font-size: 13px; padding: 8px 16px; }"
        )
        self.btn_clear.clicked.connect(self._on_clear)

        self.btn_import = QPushButton("  开始导入  ")
        self.btn_import.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; "
            "font-size: 14px; padding: 8px 20px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #218838; }"
            "QPushButton:disabled { background-color: #aaa; }"
        )
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._on_import)

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_import)
        root.addLayout(btn_row)

        # 文件列表
        grp_files = QGroupBox("已选择 PDF")
        fl = QVBoxLayout(grp_files)
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("font-size: 12px;")
        fl.addWidget(self.file_list)
        root.addWidget(grp_files)

        # 进度区（导入时显示）
        self.grp_progress = QGroupBox("导入进度")
        pl = QVBoxLayout(self.grp_progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v%")
        pl.addWidget(self.progress_bar)
        self.progress_label = QLabel("待导入")
        self.progress_label.setStyleSheet("font-size: 12px; color: #555;")
        pl.addWidget(self.progress_label)
        self.grp_progress.setVisible(False)
        root.addWidget(self.grp_progress)

        # 校验结果区
        self.grp_result = QGroupBox("导入结果")
        rl = QVBoxLayout(self.grp_result)
        self.result_label = QLabel("尚未导入")
        self.result_label.setStyleSheet("font-size: 13px; color: #999;")
        rl.addWidget(self.result_label)

        # 错误/警告表
        self.msg_table = QTableWidget(0, 3)
        self.msg_table.setHorizontalHeaderLabels(["类型", "说明", "文件"])
        self.msg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.msg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.msg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.msg_table.setEditTriggers(QTableWidget.NoEditTriggers)
        rl.addWidget(self.msg_table)
        self.grp_result.setVisible(False)
        root.addWidget(self.grp_result)

        root.addStretch()

    # ------------------------------------------------------------------ 事件

    def _on_add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择年度报告 PDF",
            "",
            "PDF 文件 (*.pdf);;所有文件 (*.*)",
        )
        if not paths:
            return
        for p in paths:
            if p not in self._pdf_paths:
                self._pdf_paths.append(p)
                item = QListWidgetItem(p)
                self.file_list.addItem(item)
        self.btn_import.setEnabled(len(self._pdf_paths) > 0)

    def _on_clear(self) -> None:
        self._pdf_paths.clear()
        self.file_list.clear()
        self.btn_import.setEnabled(False)
        self.grp_result.setVisible(False)
        self.grp_progress.setVisible(False)

    def _on_import(self) -> None:
        if not self._pdf_paths:
            return
        # 防止重复点击
        if self._worker is not None and self._worker.isRunning():
            return

        # 进入导入态：禁用按钮、显示进度条
        self.btn_add.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.btn_import.setEnabled(False)
        self.btn_import.setText("正在导入…")
        self.grp_progress.setVisible(True)
        self.grp_result.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("启动导入任务…")

        # 启动后台线程
        self._worker = ImportWorker(list(self._pdf_paths))
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, percent: int, stage: str) -> None:
        """工作线程发来的进度更新"""
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{stage}（{percent}%）")

    def _on_done(self, result_or_project_or_exc) -> None:
        """工作线程完成：可能是 ImportResult（含错误）/AnalysisProject/Exception"""
        # 重置按钮
        self.btn_add.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_import.setEnabled(True)
        self.btn_import.setText("  开始导入  ")

        # 异常分支
        if isinstance(result_or_project_or_exc, Exception):
            self.progress_bar.setValue(100)
            self.progress_label.setText("导入失败")
            QMessageBox.critical(self, "导入失败",
                                 f"导入过程发生异常：\n{result_or_project_or_exc}")
            return

        obj = result_or_project_or_exc

        # 校验失败分支：返回的是 ImportResult（含 errors/warnings）
        # 通过 hasattr 判断（避免循环引用 ImportResult 类型）
        if hasattr(obj, "errors") and hasattr(obj, "reports") and not hasattr(obj, "line_items"):
            self._show_result(obj)
            self.progress_label.setText("校验完成，请修正错误后重试")
            return

        # 正常完成分支：AnalysisProject
        if isinstance(obj, AnalysisProject):
            # 找出对应的 ImportResult 用于展示（其实 obj.year_reports 里已有信息）
            # 重新构造一个简单展示
            self.grp_result.setVisible(True)
            years = [r.year for r in obj.year_reports]
            self.result_label.setText(
                f"✅ 导入成功：{len(obj.year_reports)} 份年报"
                f"（{years[0]}—{years[-1]}），共 {len(obj.line_items)} 条科目数据"
            )
            self.result_label.setStyleSheet("font-size: 13px; color: #28a745; font-weight: bold;")
            self.msg_table.setRowCount(0)
            self.progress_label.setText(f"导入完成：{len(obj.year_reports)} 份年报")
            self.project_ready.emit(obj)
            return

    # ------------------------------------------------------------------ 辅助

    def _show_result(self, result) -> None:
        """展示 import_pdfs 返回的 errors / warnings"""
        self.grp_result.setVisible(True)
        n_reports = len(result.reports)
        n_errors = len(result.errors)
        n_warnings = len(result.warnings)
        if n_errors:
            self.result_label.setText(
                f"❌ {n_errors} 个错误，{n_warnings} 个警告，"
                f"{n_reports} 份有效年报。请修正后重新导入。"
            )
            self.result_label.setStyleSheet("font-size: 13px; color: #dc3545; font-weight: bold;")
        else:
            self.result_label.setText(
                f"✅ 导入成功：{n_reports} 份年报"
                f"（{result.reports[0].year}—{result.reports[-1].year}）"
                + (f"，{n_warnings} 个警告" if n_warnings else "")
            )
            self.result_label.setStyleSheet("font-size: 13px; color: #28a745; font-weight: bold;")

        rows = []
        for e in result.errors:
            rows.append(("错误", e.message, e.file or ""))
        for w in result.warnings:
            rows.append(("警告", w.message, w.file or ""))

        self.msg_table.setRowCount(len(rows))
        for i, (kind, msg, fname) in enumerate(rows):
            k_item = QTableWidgetItem(kind)
            if kind == "错误":
                k_item.setForeground(Qt.red)
            else:
                k_item.setForeground(Qt.darkYellow)
            self.msg_table.setItem(i, 0, k_item)
            self.msg_table.setItem(i, 1, QTableWidgetItem(msg))
            # 只显示文件名，不显示完整路径
            short = fname.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            self.msg_table.setItem(i, 2, QTableWidgetItem(short))
