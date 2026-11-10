<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AnalysisProjectData } from '../types'

const props = defineProps<{
  files: File[]
  busy: boolean
  progress: number
  progressMessage: string
  engineStatus: 'idle' | 'loading' | 'ready' | 'error'
  logs: string[]
  project: AnalysisProjectData | null
}>()
const emit = defineEmits<{
  filesSelected: [files: File[]]
  removeFile: [index: number]
  clear: []
  startImport: []
  reset: []
}>()
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const totalSize = computed(() => props.files.reduce((sum, file) => sum + file.size, 0))
const sizeLabel = computed(() => `${(totalSize.value / 1024 / 1024).toFixed(1)} MB`)

function onInput(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files?.length) emit('filesSelected', Array.from(input.files))
  input.value = ''
}
function onDrop(event: DragEvent) {
  dragging.value = false
  if (event.dataTransfer?.files.length) emit('filesSelected', Array.from(event.dataTransfer.files))
}
</script>

<template>
  <section class="page-content import-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow">STEP 01 · DATA INPUT</div>
        <h1>导入年报</h1>
        <p>选择同一家上市公司连续多年的年度报告 PDF，建议导入 5—10 年数据。</p>
      </div>
      <div class="heading-chip"><span class="chip-dot"></span>本机解析 · 不上传文件</div>
    </div>

    <div class="privacy-banner">
      <div class="privacy-icon">⌂</div>
      <div><strong>您的年报文件只在当前浏览器中处理</strong><p>PDF 将传入浏览器本机计算线程。Cloudflare 只负责提供网页资源，不接收您的年报、财务数据或分析结果。</p></div>
    </div>

    <div class="panel import-panel">
      <div class="panel-heading">
        <div><h2>选择年度报告 PDF</h2><p>支持一次选择多份文件，也可以分批添加。</p></div>
        <span class="subtle-count">{{ files.length }} 份文件</span>
      </div>

      <div
        class="dropzone"
        :class="{ dragging, disabled: busy }"
        @dragenter.prevent="dragging = true"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
        @click="!busy && fileInput?.click()"
      >
        <div class="upload-icon">↑</div>
        <strong>拖放 PDF 文件到这里</strong>
        <span>或点击选择文件，可同时选择多份年报</span>
        <button class="button button-outline" type="button" :disabled="busy" @click.stop="fileInput?.click()">选择年报 PDF</button>
        <input ref="fileInput" class="visually-hidden" type="file" accept="application/pdf,.pdf" multiple :disabled="busy" @change="onInput" />
      </div>

      <div v-if="files.length" class="file-list-wrap">
        <div class="file-list-title"><strong>已选择文件</strong><span>{{ sizeLabel }} · 可继续添加</span></div>
        <div class="file-list">
          <div v-for="(file, index) in files" :key="`${file.name}-${file.size}-${file.lastModified}`" class="file-row">
            <div class="pdf-icon">PDF</div>
            <div class="file-info"><strong>{{ file.name }}</strong><span>{{ (file.size / 1024 / 1024).toFixed(2) }} MB</span></div>
            <span class="file-state">待解析</span>
            <button class="icon-button" :disabled="busy" title="移除文件" @click="emit('removeFile', index)">×</button>
          </div>
        </div>
      </div>
      <div v-else class="empty-files">尚未添加年报文件</div>

      <div class="import-actions">
        <button class="button button-ghost" :disabled="busy || !files.length" @click="emit('clear')">清空列表</button>
        <div class="action-right"><span class="file-total" v-if="files.length">共 {{ files.length }} 份 · {{ sizeLabel }}</span><button class="button button-primary" :disabled="busy || !files.length" @click="emit('startImport')">{{ busy ? '正在导入…' : '开始导入并解析' }} <span>→</span></button></div>
      </div>
    </div>

    <div v-if="busy || engineStatus === 'loading' || engineStatus === 'ready'" class="panel progress-panel">
      <div class="panel-heading"><div><h2>本机分析引擎</h2><p>{{ progressMessage }}</p></div><span class="engine-badge" :class="engineStatus">{{ engineStatus === 'ready' ? '已就绪' : engineStatus === 'error' ? '异常' : '运行中' }}</span></div>
      <div class="progress-track"><div class="progress-fill" :style="{ width: `${Math.max(0, Math.min(progress, 100))}%` }"></div></div>
      <div class="progress-meta"><span>{{ progressMessage }}</span><strong>{{ progress }}%</strong></div>
      <div v-if="logs.length" class="log-view" aria-live="polite"><div v-for="line in logs.slice(-12)" :key="line">{{ line }}</div></div>
    </div>

    <div v-if="project" class="panel import-success">
      <div class="success-mark">✓</div><div><strong>三大财务报表解析完成</strong><p>{{ project.company.display_name }} · {{ project.years.join('、') }} 年 · {{ project.line_items.length }} 条科目记录</p></div>
      <button class="button button-outline" @click="emit('reset')">开始新的分析</button>
    </div>

    <div class="notice-grid">
      <div class="notice-card"><span>01</span><div><strong>同一家公司</strong><p>一次分析只导入同一家上市公司的年度报告。</p></div></div>
      <div class="notice-card"><span>02</span><div><strong>连续年度数据</strong><p>系统会检查年份重复、年份缺失和年报类型。</p></div></div>
      <div class="notice-card"><span>03</span><div><strong>本机运行</strong><p>首次联网下载计算资源，缓存后可离线运行。</p></div></div>
    </div>
    <p class="page-footnote">当前开发批次已接入原软件三大财务报表解析流程；非财务年报章节提取正在迁移，完成前不会显示虚构结果。</p>
  </section>
</template>
