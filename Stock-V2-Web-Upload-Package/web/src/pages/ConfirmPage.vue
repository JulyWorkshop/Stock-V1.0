<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AnalysisProjectData, LineItemData, StatementType } from '../types'

const props = defineProps<{ project: AnalysisProjectData; busy: boolean }>()
const emit = defineEmits<{ confirm: [edits: Array<{ year: number; statement_type: string; name: string; value: number }>] }>()
const statementType = ref<StatementType>('合并资产负债表')
const edits = ref<Record<string, number>>({})
const statementOptions: StatementType[] = ['合并资产负债表', '合并利润表', '合并现金流量表']
const lineMap = computed(() => {
  const map = new Map<string, LineItemData>()
  for (const item of props.project.line_items) {
    if (item.statement_type === statementType.value) map.set(`${item.year}::${item.name}`, item)
  }
  return map
})
const subjects = computed(() => {
  const names: string[] = [...(props.project.standard_subjects?.[statementType.value] || [])]
  for (const item of props.project.line_items) {
    if (item.statement_type === statementType.value && !names.includes(item.name)) names.push(item.name)
  }
  return names
})
const unrecognizedCount = computed(() => subjects.value.reduce((count, name) => count + props.project.years.filter((year) => !itemFor(year, name)?.is_recognized).length, 0))
const modifiedCount = computed(() => Object.keys(edits.value).length)
function key(year: number, name: string) { return `${statementType.value}::${year}::${name}` }
function itemFor(year: number, name: string) { return lineMap.value.get(key(year, name)) }
function displayValue(item?: LineItemData) {
  if (!item) return '0.00'
  const current = item.value ?? 0
  return Number(current).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function onValueChange(year: number, name: string, event: Event) {
  const input = event.target as HTMLInputElement
  const value = Number(input.value)
  if (!Number.isFinite(value)) return
  const item = itemFor(year, name)
  if (item && item.value !== null && Math.abs(item.value - value) < 1e-9) delete edits.value[key(year, name)]
  else edits.value[key(year, name)] = value
}
function submit() {
  const result = Object.entries(edits.value).map(([compound, value]) => {
    const [statement, yearText, name] = compound.split('::')
    const defaultUnit = props.project.line_items.find((item) => item.statement_type === statement)?.unit || '元'
    return { year: Number(yearText), statement_type: statement, name, value, unit: defaultUnit }
  })
  emit('confirm', result)
}
</script>

<template>
  <section class="page-content">
    <div class="page-heading"><div><div class="eyebrow">STEP 02 · DATA REVIEW</div><h1>数据确认</h1><p>检查自动提取的三大财务报表数据，双击或修改数值单元格可进行人工修正。</p></div><div class="heading-chip">{{ project.company.display_name }}</div></div>
    <div class="summary-strip">
      <div><span>分析公司</span><strong>{{ project.company.display_name }}</strong></div>
      <div><span>报告年度</span><strong>{{ project.years[0] }}—{{ project.years[project.years.length - 1] }}（{{ project.years.length }} 年）</strong></div>
      <div><span>科目记录</span><strong>{{ project.line_items.length }} 条</strong></div>
      <div><span>当前报表未识别</span><strong class="text-danger">{{ unrecognizedCount }} 项</strong></div>
    </div>
    <div v-if="project.warnings.length" class="warning-list"><strong>导入提示</strong><div v-for="(warning, i) in project.warnings" :key="i">{{ warning.message }}<span v-if="warning.file">（{{ warning.file }}）</span></div></div>
    <div class="panel table-panel">
      <div class="panel-heading table-toolbar"><div><h2>财务数据核对表</h2><p>未识别项目以 0 显示并标记为红色；用户修正项以蓝色标记。计算口径沿用原软件，未识别科目按 0 参与计算。</p></div><div class="toolbar-controls"><select v-model="statementType" class="select-control"><option v-for="option in statementOptions" :key="option" :value="option">{{ option }}</option></select></div></div>
      <div class="table-legend"><span><i class="legend-dot unrecognized"></i>未识别 / 按0计算</span><span><i class="legend-dot modified"></i>人工修正</span><span><i class="legend-dot normal"></i>已识别</span></div>
      <div class="table-scroll">
        <table class="data-table confirm-table">
          <thead><tr><th class="subject-col">科目</th><th v-for="year in project.years" :key="year">{{ year }}</th><th>来源页</th></tr></thead>
          <tbody>
            <tr v-for="name in subjects" :key="name">
              <th class="subject-cell">{{ name }}</th>
              <td v-for="year in project.years" :key="year" :class="{ 'cell-unrecognized': !itemFor(year, name)?.is_recognized, 'cell-modified': edits[key(year, name)] !== undefined || itemFor(year, name)?.is_modified }">
                <input class="number-cell" type="number" step="any" :value="edits[key(year, name)] ?? displayValue(itemFor(year, name)).replaceAll(',', '')" :title="itemFor(year, name) ? `${itemFor(year, name)?.source_pdf || ''} 第 ${itemFor(year, name)?.source_page || '—'} 页` : '未识别，当前按0计算；如有原始值可手工补充'" @change="onValueChange(year, name, $event)" />
              </td>
              <td class="source-cell">{{ project.line_items.find((item) => item.statement_type === statementType && item.name === name && item.source_page)?.source_page || '—' }}</td>
            </tr>
            <tr v-if="!subjects.length"><td :colspan="project.years.length + 2" class="empty-cell">当前报表没有提取到科目，请检查 PDF 或切换其他报表。</td></tr>
          </tbody>
        </table>
      </div>
      <div class="table-footer"><span>当前报表 {{ subjects.length }} 个科目 · 已人工修改 {{ modifiedCount }} 项</span><span>数值单位以单元格对应的年报原始单位为准</span></div>
    </div>
    <div class="confirm-bottom"><div><strong>确认数据后开始分析</strong><p>系统将执行财务真实性检测和18步规则分析。进入分析后仍可重新计算。</p></div><button class="button button-primary" :disabled="busy || !subjects.length" @click="submit">{{ busy ? '正在计算…' : '确认数据并开始分析' }} <span>→</span></button></div>
  </section>
</template>
