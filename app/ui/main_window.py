# -*- coding: utf-8 -*-
"""主窗口 - 侧边导航 + 5 页面栈"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QListWidget, QListWidgetItem, QLabel, QStatusBar,
)

from app.config import APP_NAME, APP_VERSION
from app.models.project import AnalysisProject
from app.ui.pages.import_page import ImportPage
from app.ui.pages.confirm_page import ConfirmPage
from app.ui.pages.overview_page import OverviewPage
from app.ui.pages.steps18_page import Steps18Page
from app.ui.pages.authenticity_page import AuthenticityPage


class MainWindow(QMainWindow):
    """主窗口：左侧导航 + 右侧页面栈"""

    # 信号：当前项目变更（导入新项目或修改数据）
    project_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} V{APP_VERSION}")
        self.resize(1280, 800)

        # 当前分析项目（None 表示未加载）
        self.project: AnalysisProject | None = None

        self._build_ui()
        self._build_statusbar()
        self._build_menubar()

        # 激活所有页面（已实现三大表解析与基础分析）
        self._set_active_pages({0, 1, 2, 3, 4})

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # 左侧导航
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setContentsMargins(0, 0, 0, 0)
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: none;
                font-size: 14px;
                outline: none;
            }
            QListWidget::item {
                padding: 16px 20px;
                border-left: 3px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #e3e3e3;
                border-left: 3px solid #2c7be5;
                color: #2c7be5;
                font-weight: bold;
            }
            QListWidget::item:disabled {
                color: #b0b0b0;
            }
        """)
        nav_items = [
            ("1. 导入年报", "import"),
            ("2. 数据确认", "confirm"),
            ("3. 企业体检总览", "overview"),
            ("4. 财务真实性检测", "authenticity"),
            ("5. 18 步详细分析", "steps18"),
        ]
        for label, _key in nav_items:
            item = QListWidgetItem(label)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        h_layout.addWidget(self.nav_list)

        # 右侧页面栈
        self.stack = QStackedWidget()
        h_layout.addWidget(self.stack, 1)

        # 创建 5 个页面（按用户要求调整顺序：真实性检测放第 4，18步放第 5）
        self.import_page = ImportPage()
        self.confirm_page = ConfirmPage()
        self.overview_page = OverviewPage()
        self.authenticity_page = AuthenticityPage()
        self.steps18_page = Steps18Page()

        # 页面 ↔ 主窗口 信号连接
        self.import_page.project_ready.connect(self._on_project_ready)

        self.stack.addWidget(self.import_page)        # index 0
        self.stack.addWidget(self.confirm_page)        # index 1
        self.stack.addWidget(self.overview_page)       # index 2
        self.stack.addWidget(self.authenticity_page)  # index 3
        self.stack.addWidget(self.steps18_page)        # index 4

        self.stack.setCurrentIndex(0)

    def _build_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")

    def _build_menubar(self) -> None:
        menubar = self.menuBar()
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _set_active_pages(self, indices: set[int]) -> None:
        """启用/禁用导航项"""
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            flags = item.flags()
            if i in indices:
                item.setFlags(flags | Qt.ItemIsEnabled)
            else:
                item.setFlags(flags & ~Qt.ItemIsEnabled)

    def _on_nav_changed(self, row: int) -> None:
        if not self.nav_list.item(row) or not (self.nav_list.item(row).flags() & Qt.ItemIsEnabled):
            return
        self.stack.setCurrentIndex(row)

    def _on_project_ready(self, project: AnalysisProject) -> None:
        """导入页完成 PDF 解析，切换到确认页"""
        self.project = project
        self.confirm_page.load_project(project)
        # 执行规则引擎（22 条规则全部计算）
        from app.rules.engine import apply_all
        apply_all(project)
        # 各页面加载项目
        self.overview_page.load_project(project)
        self.authenticity_page.load_project(project)
        self.steps18_page.load_project(project)
        self.project_changed.emit()
        # 激活所有页面
        self._set_active_pages({0, 1, 2, 3, 4})
        self.nav_list.setCurrentRow(1)
        self.status.showMessage(
            f"已加载项目：{project.company.display_name()}，"
            f"年份 {project.get_years()[0]}—{project.get_years()[-1]}，"
            f"共 {len(project.line_items)} 条科目数据"
        )

    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "关于",
            f"<h3>{APP_NAME} V{APP_VERSION}</h3>"
            "<p>上市公司财务体检工具 / 基于年报的价值投资企业分析工具</p>"
            "<p>完全本地运行，禁止 AI/联网/买卖建议。</p>"
            "<p>所有阈值严格依据 12 周课程 PDF 原文。</p>"
        )
