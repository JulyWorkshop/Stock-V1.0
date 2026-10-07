# -*- coding: utf-8 -*-
"""股票价值投资财报分析软件 V1.0 - 主入口"""
import sys
import os

# 兼容开发环境：若 pdf_libs 存在则加入 sys.path
_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pdf_libs")
if os.path.isdir(_LIB_DIR):
    sys.path.insert(0, os.path.abspath(_LIB_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow
from app.config import APP_NAME, APP_VERSION


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
