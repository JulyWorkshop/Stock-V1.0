# Stock V1.0 当前代码审查记录

审查日期：2026-11-10  
审查分支：`web-v2-validation`

## 1. 仓库与分支
- 仓库：`JulyWorkshop/Stock-V1.0`
- Web分支：`web-v2-validation`
- 分支基于Windows V1.0。
- 当前分支尚无正式Vue Web工程。

## 2. 当前技术栈
Python 3.14+、PySide6、PyMuPDF、pandas、openpyxl、pdfplumber、pyqtgraph、SQLite、PyInstaller。requirements还列有reportlab、pytest。

## 3. 核心代码
- `app/ui/main_window.py`：五页面导航与页面栈。
- `app/ui/pages/import_page.py`：多PDF导入、QThread后台解析。
- `app/ui/pages/confirm_page.py`：数据确认和人工修正。
- `app/ui/pages/overview_page.py`：企业体检总览。
- `app/ui/pages/authenticity_page.py`：财务真实性检测。
- `app/ui/pages/steps18_page.py`：18步分析。
- `app/pdf/importer.py`：文件可读性、扫描版、公司、年报、年份校验。
- `app/pdf/parsers/table_parser.py`：PyMuPDF表格识别。
- `app/pdf/parsers/balance_sheet.py`、`income_statement.py`、`cash_flow.py`：文本解析回退。
- `app/pdf/parsers/fallback_scan.py`：补漏扫描。
- `app/calculation/formulas.py`：财务公式。
- `app/rules/engine.py`：规则执行、状态、结论。
- `app/rules/thresholds.py`、`rules.json`：规则和阈值。
- `app/models/`：数据模型。
- `app/data/repository.py`：SQLite项目读写函数。
- `app/export/`：目前仅有初始化文件；但网页版已取消报告导出，因此不需要为网页实现此模块。

## 4. 当前五页面顺序
`main_window.py`实际顺序：
1. 导入年报
2. 数据确认
3. 企业体检总览
4. 财务真实性检测
5. 18步详细分析

需求书第44节页面4/5顺序与当前代码相反。Web版按用户确认，以当前Windows软件实际顺序为准。

## 5. 当前导入逻辑
`ImportPage`使用`QFileDialog.getOpenFileNames()`支持一次选择多份PDF；`ImportWorker`使用`QThread`执行解析并报告进度。流程调用`import_pdfs(paths)`，逐年解析三大财务报表，优先表格解析，按原条件回退文本解析，再执行补漏扫描，最终组装`AnalysisProject`。

## 6. 已知差异与迁移风险
1. 当前主窗口启动时启用全部五页；Web版需增加未导入/未确认时的页面门控。
2. `rules.json`当前25条记录，其中step=0真实性规则8条、step=3—18规则17条；`engine.py`注释仍写22条，需核对。
3. 18步规则记录覆盖step 3—18；step 1、2在页面框架展示但无对应规则结果。
4. `authenticity_page.py`顶部注释描述5条真实性规则，而规则文件有8条step=0记录，需核实实际映射。
5. `LineItem.safe_value` / `safe_value_in_yuan`在缺失时返回0，公式模块也注明未识别科目按0计算；用户已明确继续采用按0计算的口径。
6. 当前主窗口在`project_ready`后立即执行`apply_all(project)`；Web版按需求需先完成数据确认，再正式分析。
7. SQLite `save_project/load_project`已存在，但主窗口未发现保存/打开UI；用户明确不需要网页版项目自动保存和恢复。
8. 原需求书第12节规定的非财务信息提取在当前已审查的导入主流程和页面代码中未发现完整实现；网页版必须按原需求补齐。
9. 原需求书第32节包含大量补充指标，当前25条规则记录并未完整体现所有指标；需建立逐项覆盖矩阵并补齐。
10. 原需求书第44节页面4/5顺序与当前源代码相反；按当前代码顺序迁移。

## 7. 用户本机验证
用户于2026-11-10提供Windows 11验证日志：Python 3.14.2、PyMuPDF 1.27.2.2、`fitz`兼容导入成功、样本PDF 143页、候选页9页、发现表格13张、Service Worker和Pyodide资源缓存已建立。

这证明浏览器能加载Python/PyMuPDF并对样本执行基础页面定位和表格发现；尚未证明原有三大报表解析、完整非财务信息提取、勾稽校验、规则计算和完整离线流程通过。

## 8. 用户确认的迁移边界
- 不做项目自动保存/恢复。
- 不长期保存原始PDF。
- 分析数据只在当前浏览器会话内存中处理。
- 结果直接在浏览器页面展示。
- 不开发Excel/PDF导出。
- 未识别科目按0计算。
- 原需求书中除报告导出外的分析功能必须保留。
