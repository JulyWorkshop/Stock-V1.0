# 股票价值投资财报分析软件 V1.0

Windows 11 桌面应用，导入 A 股上市公司多年年报 PDF，自动提取财务数据，依据课程 18 步框架生成可验证、可重复的企业财务体检报告。

## 严格约束

- 完全本地运行、完全离线
- 禁止 AI、联网、行情、估值、买卖建议
- 同一输入每次结果完全一致
- 每个数据点保留来源 PDF+页码
- 未识别不猜，由用户人工补

## 开发环境

- Python 3.14+
- 依赖：PySide6、pandas、PyMuPDF、openpyxl、pyqtgraph、PyInstaller

## 安装

```bat
cd ffa
pip install -r requirements.txt
```

## 运行（开发模式）

```bat
python main.py
```

## 打包 EXE

```bat
build.bat
```

## 项目结构

见 `.trae/documents/股票价值投资财报分析软件V1.0-实施计划.md`

## 阈值来源

所有数值阈值严格依据 12 份课程 PDF 原文，集中在 `rules.json`，每条标注课程出处（周次+页码）。课程未明确的，不发明阈值，只显示数值与趋势。
