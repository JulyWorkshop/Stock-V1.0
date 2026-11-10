<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ImportPage from './pages/ImportPage.vue'
import ConfirmPage from './pages/ConfirmPage.vue'
import OverviewPage from './pages/OverviewPage.vue'
import AuthenticityPage from './pages/AuthenticityPage.vue'
import Steps18Page from './pages/Steps18Page.vue'
import type { AnalysisProjectData, PageKey } from './types'

const navItems: Array<{ key: PageKey; title: string; subtitle: string; number: string }> = [
  { key: 'import', title: '导入年报', subtitle: 'Import reports', number: '01' },
  { key: 'confirm', title: '数据确认', subtitle: 'Review data', number: '02' },
  { key: 'overview', title: '企业体检总览', subtitle: 'Company overview', number: '03' },
  { key: 'authenticity', title: '财务真实性检测', subtitle: 'Authenticity checks', number: '04' },
  { key: 'steps18', title: '18 步详细分析', subtitle: '18-step analysis', number: '05' },
]

const activePage = ref<PageKey>('import')
const selectedFiles = ref<File[]>([])
const project = ref<AnalysisProjectData | null>(null)
const isBusy = ref(false)
const progress = ref(0)
const progressMessage = ref('等待导入年报')
const engineStatus = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const errorMessage = ref('')
const logMessages = ref<string[]>([])
const isOnline = ref(navigator.onLine)
let worker: Worker | null = null
const pending = new Map<string, { resolve: (value: any) => void; reject: (reason: Error) => void }>()
const isImported = computed(() => Boolean(project.value && project.value.reports.length))
const isAnalyzed = computed(() => Boolean(project.value && project.value.rule_results.length))
const currentTitle = computed(() => navItems.find((item) => item.key === activePage.value)?.title || 'Stock V2.0')
const currentCompany = computed(() => project.value?.company.display_name || '')

function log(message: string) {
  const stamp = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  logMessages.value = [...logMessages.value.slice(-49), `[${stamp}] ${message}`]
}

function ensureWorker(): Worker {
  if (worker) return worker
  if (import.meta.env.PROD && 'serviceWorker' in navigator && !navigator.serviceWorker.controller) {
    throw new Error('网站离线缓存正在首次安装，请等待页面自动刷新后再开始导入。')
  }
  worker = new Worker(new URL('./workers/engine.worker.ts', import.meta.url), { type: 'module' })
  worker.onmessage = (event: MessageEvent) => {
    const data = event.data || {}
    if (data.type === 'PROGRESS') {
      progress.value = Number(data.percent ?? progress.value)
      progressMessage.value = data.message || '正在处理…'
      return
    }
    if (data.type === 'LOG') {
      log(data.message)
      return
    }
    if (data.id && pending.has(data.id)) {
      const task = pending.get(data.id)!
      pending.delete(data.id)
      if (data.ok) task.resolve(data.result)
      else task.reject(new Error(data.error || '本机计算线程发生未知错误'))
    }
  }
  worker.onerror = (event) => {
    engineStatus.value = 'error'
    errorMessage.value = event.message || '本机计算线程发生错误'
    log(`Worker 错误：${errorMessage.value}`)
  }
  return worker
}

function requestWorker(type: string, payload: Record<string, unknown> = {}, transfer: Transferable[] = []) {
  const id = crypto.randomUUID()
  return new Promise<any>((resolve, reject) => {
    try {
      const activeWorker = ensureWorker()
      pending.set(id, { resolve, reject })
      activeWorker.postMessage({ id, type, ...payload }, transfer)
    } catch (error) {
      reject(error instanceof Error ? error : new Error(String(error)))
    }
  })
}

function canOpen(key: PageKey) {
  if (key === 'import') return true
  if (key === 'confirm') return isImported.value
  return isAnalyzed.value
}

function navigate(key: PageKey) {
  if (!canOpen(key)) return
  activePage.value = key
}

function addFiles(files: File[]) {
  const pdfs = files.filter((file) => file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf')
  const seen = new Set(selectedFiles.value.map((file) => `${file.name}:${file.size}:${file.lastModified}`))
  selectedFiles.value = [...selectedFiles.value, ...pdfs.filter((file) => !seen.has(`${file.name}:${file.size}:${file.lastModified}`))]
  errorMessage.value = ''
}

function removeFile(index: number) {
  selectedFiles.value = selectedFiles.value.filter((_, i) => i !== index)
}

async function startImport() {
  if (!selectedFiles.value.length || isBusy.value) return
  isBusy.value = true
  errorMessage.value = ''
  progress.value = 0
  logMessages.value = []
  engineStatus.value = 'loading'
  try {
    log('启动浏览器本机分析引擎。PDF 不会上传服务器。')
    await requestWorker('INIT')
    engineStatus.value = 'ready'
    const fileIds: string[] = []
    for (let index = 0; index < selectedFiles.value.length; index += 1) {
      const file = selectedFiles.value[index]
      progressMessage.value = `正在将第 ${index + 1}/${selectedFiles.value.length} 份年报放入本机内存…`
      const buffer = await file.arrayBuffer()
      const fileId = crypto.randomUUID()
      await requestWorker('ADD_PDF', { fileId, name: file.name, buffer }, [buffer])
      fileIds.push(fileId)
      log(`已在本机载入：${file.name}（${(file.size / 1024 / 1024).toFixed(1)} MB）`)
    }
    const result = await requestWorker('IMPORT_BATCH', { fileIds })
    if (!result.valid) {
      project.value = null
      errorMessage.value = result.message || '年报校验未通过。'
      progressMessage.value = '文件校验未通过'
      log(errorMessage.value)
      if (result.errors?.length) {
        for (const item of result.errors) log(`${item.code}：${item.message}${item.file ? `（${item.file}）` : ''}`)
      }
      return
    }
    project.value = result.project as AnalysisProjectData
    progressMessage.value = `已完成 ${project.value.reports.length} 份年报的三大财务报表解析`
    progress.value = 100
    activePage.value = 'confirm'
    log(`解析完成：${project.value.company.display_name}，${project.value.years.join('、')} 年，${project.value.line_items.length} 条科目记录。`)
    if (project.value.non_financial.status !== 'complete') {
      log('提示：非财务章节提取尚未迁移，本阶段不会生成虚构的非财务分析。')
    }
  } catch (error: any) {
    engineStatus.value = 'error'
    errorMessage.value = error?.message || String(error)
    progressMessage.value = '导入失败'
    log(`导入失败：${errorMessage.value}`)
  } finally {
    isBusy.value = false
  }
}

async function confirmAndAnalyze(edits: Array<{ year: number; statement_type: string; name: string; value: number; unit?: string }>) {
  if (!project.value || isBusy.value) return
  isBusy.value = true
  errorMessage.value = ''
  progress.value = 0
  try {
    progressMessage.value = '正在根据确认后的数据执行分析规则…'
    const result = await requestWorker('CONFIRM_AND_ANALYZE', { edits })
    project.value = result as AnalysisProjectData
    activePage.value = 'overview'
    log(`分析完成：共生成 ${project.value.rule_results.length} 条年度规则结果。`)
  } catch (error: any) {
    errorMessage.value = error?.message || String(error)
    log(`分析失败：${errorMessage.value}`)
  } finally {
    isBusy.value = false
  }
}

async function recalculate() {
  if (!project.value || isBusy.value) return
  const edits: Array<{ year: number; statement_type: string; name: string; value: number; unit?: string }> = []
  for (const item of project.value.line_items) {
    if (item.modified_value !== null && item.modified_value !== item.original_value) {
      edits.push({ year: item.year, statement_type: item.statement_type, name: item.name, value: item.modified_value, unit: item.unit })
    }
  }
  await confirmAndAnalyze(edits)
}

function resetSession() {
  if (isBusy.value) return
  project.value = null
  selectedFiles.value = []
  activePage.value = 'import'
  progress.value = 0
  progressMessage.value = '等待导入年报'
  errorMessage.value = ''
  logMessages.value = []
  requestWorker('RESET').catch(() => undefined)
}

function handleOnline() { isOnline.value = true }
function handleOffline() { isOnline.value = false }
onMounted(() => {
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then(() => log('网站离线缓存服务已就绪。')).catch(() => undefined)
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
  worker?.terminate()
  pending.forEach((task) => task.reject(new Error('页面已关闭')))
  pending.clear()
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div class="brand-copy">
          <strong>Stock V2.0</strong>
          <span>财务体检分析系统</span>
        </div>
      </div>

      <div class="sidebar-caption">分析工作区</div>
      <nav class="main-nav" aria-label="分析页面导航">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: activePage === item.key, locked: !canOpen(item.key) }"
          :disabled="!canOpen(item.key)"
          @click="navigate(item.key)"
        >
          <span class="nav-number">{{ item.number }}</span>
          <span class="nav-labels"><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span>
          <span v-if="activePage === item.key" class="nav-current"></span>
          <span v-else-if="canOpen(item.key) && item.key !== 'import'" class="nav-check">✓</span>
        </button>
      </nav>

      <div class="sidebar-spacer"></div>
      <div class="privacy-note">
        <span class="privacy-symbol">◉</span>
        <strong>数据仅在本机处理</strong>
        <p>年报 PDF、财务数据和分析结果不会上传服务器。</p>
      </div>
      <div class="sidebar-footer">STOCK V2.0 · LOCAL FIRST</div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div class="breadcrumbs"><span>工作区</span><span class="crumb-sep">/</span><strong>{{ currentTitle }}</strong></div>
        <div class="topbar-right">
          <span class="connection-pill" :class="isOnline ? 'online' : 'offline'"><i></i>{{ isOnline ? '当前联网' : '当前离线' }}</span>
          <span class="version-pill">V2.0 · 浏览器本机版</span>
        </div>
      </header>

      <div class="page-scroll">
        <div v-if="errorMessage" class="global-error" role="alert">
          <span>!</span><div>{{ errorMessage }}</div><button @click="errorMessage = ''">关闭</button>
        </div>

        <ImportPage
          v-if="activePage === 'import'"
          :files="selectedFiles"
          :busy="isBusy"
          :progress="progress"
          :progress-message="progressMessage"
          :engine-status="engineStatus"
          :logs="logMessages"
          :project="project"
          @files-selected="addFiles"
          @remove-file="removeFile"
          @clear="selectedFiles = []; errorMessage = ''; progress = 0; progressMessage = '等待导入年报'"
          @start-import="startImport"
          @reset="resetSession"
        />
        <ConfirmPage
          v-else-if="activePage === 'confirm' && project"
          :project="project"
          :busy="isBusy"
          @confirm="confirmAndAnalyze"
        />
        <OverviewPage
          v-else-if="activePage === 'overview' && project"
          :project="project"
          :busy="isBusy"
          @recalculate="recalculate"
          @open-authenticity="navigate('authenticity')"
          @open-steps="navigate('steps18')"
        />
        <AuthenticityPage
          v-else-if="activePage === 'authenticity' && project"
          :project="project"
          :busy="isBusy"
          @recalculate="recalculate"
        />
        <Steps18Page
          v-else-if="activePage === 'steps18' && project"
          :project="project"
          :busy="isBusy"
          @recalculate="recalculate"
        />
      </div>

      <footer class="statusbar">
        <span><i class="status-dot" :class="isBusy ? 'working' : 'ready'"></i>{{ isBusy ? progressMessage : (currentCompany || '就绪') }}</span>
        <span>{{ project ? `${project.years.length} 个年度 · ${project.line_items.length} 条科目数据` : '尚未载入分析项目' }}</span>
      </footer>
    </main>
  </div>
</template>
