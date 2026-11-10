/*
 * Stock V2.0 browser-local analysis worker.
 * PDF bytes and all financial data remain inside this browser worker / Pyodide memory.
 * No PDF, financial data or analysis result is sent to any server.
 */
const PYODIDE_VERSION = '314.0.6'
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`
const PYODIDE_MODULE_URL = `${PYODIDE_BASE}pyodide.mjs`

const CORE_FILES = [
  'app/__init__.py',
  'app/config.py',
  'app/models/__init__.py',
  'app/models/company.py',
  'app/models/line_item.py',
  'app/models/project.py',
  'app/models/rule.py',
  'app/models/statements.py',
  'app/pdf/__init__.py',
  'app/pdf/importer.py',
  'app/pdf/page_locator.py',
  'app/pdf/unit_detector.py',
  'app/pdf/subject_alias.py',
  'app/pdf/parsers/__init__.py',
  'app/pdf/parsers/balance_sheet.py',
  'app/pdf/parsers/income_statement.py',
  'app/pdf/parsers/cash_flow.py',
  'app/pdf/parsers/fallback_scan.py',
  'app/pdf/parsers/table_parser.py',
  'app/calculation/__init__.py',
  'app/calculation/formulas.py',
  'app/rules/__init__.py',
  'app/rules/engine.py',
  'app/rules/thresholds.py',
  'rules.json',
]

let pyodide: any = null
let initPromise: Promise<void> | null = null
let storedFiles = new Map<string, { name: string; path: string }>()

function sendProgress(message: string, percent?: number) {
  self.postMessage({ type: 'PROGRESS', message, percent })
}

function sendLog(message: string) {
  self.postMessage({ type: 'LOG', message })
}

async function initRuntime() {
  if (initPromise) return initPromise
  initPromise = (async () => {
    try {
      sendProgress('正在加载浏览器本机 Python 运行环境…', 3)
      // Pyodide is intentionally loaded from the version-pinned CDN; the Service Worker caches it after first use.
      // @ts-ignore - remote ESM module is loaded by the browser at runtime
      const { loadPyodide } = await import(/* @vite-ignore */ PYODIDE_MODULE_URL)
      pyodide = await loadPyodide({
        indexURL: PYODIDE_BASE,
        stdout: (line: string) => sendLog(`[Python] ${line}`),
        stderr: (line: string) => sendLog(`[Python stderr] ${line}`),
      })

      sendProgress('正在加载 PyMuPDF 并安装原软件分析模块…', 10)
      await pyodide.loadPackage('PyMuPDF')

      for (let index = 0; index < CORE_FILES.length; index += 1) {
        const relativePath = CORE_FILES[index]
        const response = await fetch(`/python/${relativePath}`, { cache: 'no-cache' })
        if (!response.ok) throw new Error(`加载核心模块失败：${relativePath}（HTTP ${response.status}）`)
        const source = await response.text()
        const targetPath = relativePath === 'rules.json' ? '/app/rules.json' : `/app/${relativePath}`
        const parent = targetPath.slice(0, targetPath.lastIndexOf('/'))
        pyodide.FS.mkdirTree(parent)
        pyodide.FS.writeFile(targetPath, source, { encoding: 'utf8' })
        const percent = 10 + Math.round(((index + 1) / CORE_FILES.length) * 35)
        sendProgress(`正在加载原软件核心模块（${index + 1}/${CORE_FILES.length}）：${relativePath}`, percent)
      }

      pyodide.runPython(`
import sys
sys.path.insert(0, "/app")
import pymupdf
import fitz
from app.pdf.importer import import_pdfs
from app.pdf.parsers.table_parser import parse_statement_by_table
from app.rules.engine import apply_all
from app.rules.thresholds import load_rules
      `)
      const versions = JSON.parse(pyodide.runPython(`
import json, sys, pymupdf
json.dumps({"python": sys.version.split()[0], "pymupdf": getattr(pymupdf, "VersionBind", "unknown")}, ensure_ascii=False)
      `))
      sendLog(`Python ${versions.python}；PyMuPDF ${versions.pymupdf}；原软件核心模块导入成功。`)
      sendProgress('本机分析引擎已就绪。', 50)
    } catch (error: any) {
      initPromise = null
      pyodide = null
      throw new Error(error?.stack || error?.message || String(error))
    }
  })()
  return initPromise
}

function serializeProject() {
  const raw = pyodide.runPython(`
import json
from app.rules.thresholds import load_rules
_rule_list, _subject_groups = load_rules()
_rule_meta = {r.id: r for r in _rule_list}

def _line_item_dict(li):
    return {
        "year": li.year,
        "statement_type": li.statement_type,
        "name": li.name,
        "aliases": list(li.aliases or []),
        "original_value": li.original_value,
        "modified_value": li.modified_value,
        "value": li.value,
        "unit": li.unit,
        "source_pdf": li.source_pdf,
        "source_page": li.source_page,
        "is_recognized": bool(li.is_recognized),
        "is_modified": bool(li.is_modified),
    }

json.dumps({
  "company": {
    "name": project.company.name,
    "stock_code": project.company.stock_code,
    "display_name": project.company.display_name(),
  },
  "years": project.get_years(),
  "reports": [
    {
      "year": r.year,
      "file_name": r.pdf_path,
      "report_title": r.report_title,
      "is_scanned": bool(r.is_scanned),
      "parse_warnings": list(r.parse_warnings or []),
    } for r in project.year_reports
  ],
  "line_items": [_line_item_dict(li) for li in project.line_items],
  "standard_subjects": {
    "合并资产负债表": __import__('app.pdf.subject_alias', fromlist=['list_standard_subjects']).list_standard_subjects('合并资产负债表'),
    "合并利润表": __import__('app.pdf.subject_alias', fromlist=['list_standard_subjects']).list_standard_subjects('合并利润表'),
    "合并现金流量表": __import__('app.pdf.subject_alias', fromlist=['list_standard_subjects']).list_standard_subjects('合并现金流量表')
  },
  "rule_results": [
    {
      "rule_id": r.rule_id,
      "rule_name": r.rule_name,
      "year": r.year,
      "actual_value": r.actual_value,
      "reference_value": r.reference_value,
      "status": r.status.value,
      "conclusion": r.conclusion,
      "evidence": [_line_item_dict(li) for li in (r.evidence or [])],
      "course_source": r.course_source,
      "is_calculable": bool(r.is_calculable),
      "step": _rule_meta[r.rule_id].step if r.rule_id in _rule_meta else 0,
    } for r in project.rule_results
  ],
  "rules": [
    {
      "id": r.id,
      "name": r.name,
      "step": r.step,
      "thresholds": r.thresholds,
      "description": r.description,
      "course_source": r.course_source,
    } for r in _rule_list
  ],
  "errors": [],
  "warnings": json.loads(globals().get("stock_validation_warnings_json", "[]")),
  "non_financial": {
    "status": "not_started",
    "message": "非财务年报章节提取模块尚未迁移；此版本不会伪造提取结果。",
    "sections": []
  }
}, ensure_ascii=False)
`)
  return JSON.parse(raw)
}

async function addPdf(id: string, name: string, buffer: ArrayBuffer) {
  await initRuntime()
  const safeId = id.replace(/[^a-zA-Z0-9_-]/g, '_')
  const path = `/tmp/stock-v2/${safeId}.pdf`
  pyodide.FS.mkdirTree('/tmp/stock-v2')
  pyodide.FS.writeFile(path, new Uint8Array(buffer))
  storedFiles.set(id, { name, path })
  return { id, name, size: buffer.byteLength }
}

async function importBatch(ids: string[]) {
  await initRuntime()
  const selected = ids.map((id) => storedFiles.get(id)).filter(Boolean) as Array<{ name: string; path: string }>
  if (!selected.length) throw new Error('没有可供解析的 PDF 文件。')
  sendProgress(`正在校验 ${selected.length} 份年报：检查公司、年份、年报类型和PDF可读性…`, 52)
  pyodide.globals.set('stock_pdf_paths_json', JSON.stringify(selected.map((file) => file.path)))
  const importRaw = pyodide.runPython(`
import json
from app.pdf.importer import import_pdfs
_stock_import_result = import_pdfs(json.loads(stock_pdf_paths_json))
json.dumps({
  "reports": [{"year": r.year, "path": r.pdf_path, "report_title": r.report_title, "is_scanned": r.is_scanned, "parse_warnings": r.parse_warnings} for r in _stock_import_result.reports],
  "errors": [{"code": e.code, "message": e.message, "file": e.file, "year": e.year} for e in _stock_import_result.errors],
  "warnings": [{"code": w.code, "message": w.message, "file": w.file, "year": w.year} for w in _stock_import_result.warnings]
}, ensure_ascii=False)
`)
  const validation = JSON.parse(importRaw)
  const nameByPath = new Map(selected.map((file) => [file.path, file.name]))
  validation.errors = validation.errors.map((item: any) => ({ ...item, file: nameByPath.get(item.file) || item.file }))
  validation.warnings = validation.warnings.map((item: any) => ({ ...item, file: nameByPath.get(item.file) || item.file }))

  if (validation.errors.length || !validation.reports.length) {
    for (const file of selected) {
      try { pyodide.FS.unlink(file.path) } catch (_) {}
      storedFiles.delete(ids.find((id) => storedFiles.get(id)?.path === file.path) || '')
    }
    return {
      valid: false,
      errors: validation.errors,
      warnings: validation.warnings,
      reports: validation.reports,
      message: validation.errors.length ? '文件校验未通过，请根据错误信息调整年报文件。' : '没有识别到可用的年度报告。',
    }
  }

  sendProgress(`文件校验通过，正在解析 ${validation.reports.length} 个年度的三大财务报表…`, 60)
  const reportPaths = validation.reports.map((report: any) => report.path)
  pyodide.globals.set('stock_validation_warnings_json', JSON.stringify(validation.warnings))
  pyodide.globals.set('stock_report_paths_json', JSON.stringify(reportPaths))
  pyodide.runPython(`
import json, os
from app.models.project import AnalysisProject
from app.pdf.parsers.balance_sheet import parse_balance_sheet
from app.pdf.parsers.income_statement import parse_income_statement
from app.pdf.parsers.cash_flow import parse_cash_flow
from app.pdf.parsers.fallback_scan import fallback_scan
from app.pdf.parsers.table_parser import parse_statement_by_table
_stock_all_items = []
_stock_reports = _stock_import_result.reports
_stock_company = _stock_reports[0].company
_stock_paths = json.loads(stock_report_paths_json)
for _stock_i, _stock_rpt in enumerate(_stock_reports):
    _stock_path = _stock_rpt.pdf_path
    print(f"开始解析 {_stock_rpt.year} 年报（{_stock_i + 1}/{len(_stock_reports)}）")
    _stock_bs = parse_statement_by_table(_stock_path, _stock_rpt.year, "合并资产负债表", _stock_company.name)
    if sum(1 for _li in _stock_bs if _li.is_recognized) < 20:
        _stock_bs = parse_balance_sheet(_stock_path, _stock_rpt.year, _stock_company.name)
    _stock_all_items.extend(_stock_bs)
    _stock_ic = parse_statement_by_table(_stock_path, _stock_rpt.year, "合并利润表", _stock_company.name)
    if sum(1 for _li in _stock_ic if _li.is_recognized) < 10:
        _stock_ic = parse_income_statement(_stock_path, _stock_rpt.year, _stock_company.name)
    _stock_all_items.extend(_stock_ic)
    _stock_cf = parse_statement_by_table(_stock_path, _stock_rpt.year, "合并现金流量表", _stock_company.name)
    if sum(1 for _li in _stock_cf if _li.is_recognized) < 10:
        _stock_cf = parse_cash_flow(_stock_path, _stock_rpt.year, _stock_company.name)
    _stock_all_items.extend(_stock_cf)
    _stock_bs_found = {_li.name for _li in _stock_bs if _li.is_recognized}
    _stock_ic_found = {_li.name for _li in _stock_ic if _li.is_recognized}
    _stock_cf_found = {_li.name for _li in _stock_cf if _li.is_recognized}
    _stock_all_items.extend(fallback_scan(_stock_path, _stock_rpt.year, "合并资产负债表", _stock_bs_found, _stock_company.name))
    _stock_all_items.extend(fallback_scan(_stock_path, _stock_rpt.year, "合并利润表", _stock_ic_found, _stock_company.name))
    _stock_all_items.extend(fallback_scan(_stock_path, _stock_rpt.year, "合并现金流量表", _stock_cf_found, _stock_company.name))
_stock_project = AnalysisProject(company=_stock_company, year_reports=list(_stock_reports), line_items=_stock_all_items)
`)
  pyodide.globals.set('stock_name_by_path_json', JSON.stringify(Object.fromEntries(nameByPath)))
  pyodide.runPython(`
import json, os
_stock_name_by_path = json.loads(stock_name_by_path_json)
for _r in _stock_project.year_reports:
    _r.pdf_path = _stock_name_by_path.get(_r.pdf_path, os.path.basename(_r.pdf_path))
for _li in _stock_project.line_items:
    _li.source_pdf = _stock_name_by_path.get(_li.source_pdf, os.path.basename(_li.source_pdf))
project = _stock_project
`)
  sendProgress('三大财务报表解析完成，正在整理数据确认表…', 95)
  const project = serializeProject()
  project.warnings = validation.warnings
  project.errors = []

  // The original PDF bytes are removed from the in-memory filesystem once parsing is finished.
  for (const file of selected) {
    try { pyodide.FS.unlink(file.path) } catch (_) {}
    storedFiles.delete(ids.find((id) => storedFiles.get(id)?.path === file.path) || '')
  }
  sendProgress('年报导入和三大财务报表解析完成。', 100)
  return { valid: true, project }
}

async function confirmAndAnalyze(edits: Array<{ year: number; statement_type: string; name: string; value: number }>) {
  await initRuntime()
  pyodide.globals.set('stock_edits_json', JSON.stringify(edits))
  pyodide.runPython(`
import json
from app.models.line_item import LineItem
_stock_edits = json.loads(stock_edits_json)
for _edit in _stock_edits:
    _li = project.get_line_item(int(_edit["year"]), _edit["name"], _edit["statement_type"])
    if _li is None:
        _li = LineItem(
            year=int(_edit["year"]), statement_type=_edit["statement_type"], name=_edit["name"],
            aliases=[], original_value=None, modified_value=float(_edit["value"]), unit=_edit.get("unit", "元"),
            source_pdf="", source_page=0, is_recognized=False
        )
        project.line_items.append(_li)
    else:
        _li.modified_value = float(_edit["value"])
from app.rules.engine import apply_all
apply_all(project)
`)
  sendProgress('18步规则和财务真实性检测已完成，正在生成网页结果数据…', 100)
  return serializeProject()
}

self.onmessage = async (event: MessageEvent) => {
  const data = event.data || {}
  const id = data.id
  try {
    let result: any
    if (data.type === 'INIT') {
      await initRuntime()
      result = { ready: true, pyodideVersion: PYODIDE_VERSION }
    } else if (data.type === 'ADD_PDF') {
      result = await addPdf(data.fileId, data.name, data.buffer)
    } else if (data.type === 'IMPORT_BATCH') {
      result = await importBatch(data.fileIds || [])
    } else if (data.type === 'CONFIRM_AND_ANALYZE') {
      result = await confirmAndAnalyze(data.edits || [])
    } else if (data.type === 'RESET') {
      storedFiles.clear()
      try { pyodide?.runPython('project = None') } catch (_) {}
      result = { reset: true }
    } else {
      throw new Error(`未知 Worker 命令：${data.type}`)
    }
    self.postMessage({ id, ok: true, result })
  } catch (error: any) {
    self.postMessage({ id, ok: false, error: error?.stack || error?.message || String(error) })
  }
}
