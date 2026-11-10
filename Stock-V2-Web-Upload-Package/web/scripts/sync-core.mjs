import { cp, mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(webRoot, '..')
const outputRoot = join(webRoot, 'public', 'python')

// These are the existing Windows V1.0 business modules used by the browser Worker.
// Keep this list aligned with CORE_FILES in src/workers/engine.worker.ts.
const coreFiles = [
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
]

await rm(outputRoot, { recursive: true, force: true })
await mkdir(outputRoot, { recursive: true })

for (const relativePath of coreFiles) {
  const sourcePath = join(repositoryRoot, relativePath)
  try {
    await stat(sourcePath)
  } catch {
    throw new Error(`缺少 Windows V1.0 核心模块：${relativePath}。请确认 web/ 与 app/ 位于同一仓库根目录。`)
  }
  const destinationPath = join(outputRoot, relativePath)
  await mkdir(dirname(destinationPath), { recursive: true })
  await cp(sourcePath, destinationPath)
}

const rulesSource = join(repositoryRoot, 'rules.json')
const rulesDestination = join(outputRoot, 'rules.json')
await writeFile(rulesDestination, await readFile(rulesSource))

console.log(`[Stock V2.0] 已同步 ${coreFiles.length} 个原 Python 模块和 rules.json 到 public/python。`)
