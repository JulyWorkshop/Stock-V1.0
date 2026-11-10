<script setup lang="ts">
import { computed } from 'vue'
import type { AnalysisProjectData, RuleResultData } from '../types'

const props = defineProps<{ project: AnalysisProjectData; busy: boolean }>()
const emit = defineEmits<{ recalculate: []; openAuthenticity: []; openSteps: [] }>()
const grouped = computed(() => {
  const map = new Map<string, { name: string; source: string; byYear: Map<number, RuleResultData> }>()
  for (const result of props.project.rule_results) {
    if (!map.has(result.rule_id)) map.set(result.rule_id, { name: result.rule_name, source: result.course_source, byYear: new Map() })
    map.get(result.rule_id)!.byYear.set(result.year, result)
  }
  return Array.from(map.entries()).map(([id, value]) => ({ id, ...value }))
})
const latestYear = computed(() => props.project.years[props.project.years.length - 1])
const latestResults = computed(() => props.project.rule_results.filter((item) => item.year === latestYear.value))
const counts = computed(() => {
  const result: Record<string, number> = { 优势: 0, 一般: 0, 关注: 0, 高风险: 0, 淘汰: 0, 不适用: 0 }
  for (const item of latestResults.value) result[item.status] = (result[item.status] || 0) + 1
  return result
})
function formatValue(result?: RuleResultData) {
  if (!result || result.actual_value === null) return result?.status || '—'
  if (typeof result.actual_value === 'object') return JSON.stringify(result.actual_value)
  const id = result.rule_id
  const isRatio = /ratio|margin|roe|growth|yield/.test(id) || id.endsWith('_cash_ratio')
  return isRatio ? `${(result.actual_value * 100).toFixed(2)}%` : Number(result.actual_value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function statusClass(status?: string) { return `status-${(status || '不适用').replaceAll('/', '-')}` }
</script>

<template>
  <section class="page-content">
    <div class="page-heading"><div><div class="eyebrow">STEP 03 · COMPANY CHECKUP</div><h1>企业体检总览</h1><p>按年度汇总规则执行结果，查看企业主要优势与需要关注的财务指标。</p></div><button class="button button-outline" :disabled="busy" @click="emit('recalculate')">↻ 重新计算</button></div>
    <div class="company-banner"><div class="company-avatar">{{ project.company.name.slice(0, 1) || '企' }}</div><div class="company-main"><strong>{{ project.company.display_name }}</strong><span>{{ project.company.stock_code ? `证券代码 ${project.company.stock_code}` : '上市公司年度报告分析' }} · {{ project.years[0] }}—{{ latestYear }}</span></div><div class="company-meta"><span>分析年度</span><strong>{{ project.years.length }} 年</strong></div><div class="company-meta"><span>规则结果</span><strong>{{ project.rule_results.length }} 条</strong></div></div>
    <div class="metric-cards">
      <div class="metric-card advantage"><span>优势</span><strong>{{ counts['优势'] }}</strong><small>最新年度</small></div>
      <div class="metric-card normal"><span>一般 / 正常</span><strong>{{ counts['一般'] }}</strong><small>最新年度</small></div>
      <div class="metric-card attention"><span>关注</span><strong>{{ counts['关注'] }}</strong><small>最新年度</small></div>
      <div class="metric-card risk"><span>高风险 / 淘汰</span><strong>{{ counts['高风险'] + counts['淘汰'] }}</strong><small>最新年度</small></div>
    </div>
    <div class="panel table-panel">
      <div class="panel-heading"><div><h2>年度体检结果矩阵</h2><p>每个单元格显示状态与实际值；悬停可查看规则结论。</p></div><span class="subtle-count">{{ latestYear }} 年最新结果</span></div>
      <div class="table-scroll"><table class="data-table overview-table"><thead><tr><th class="subject-col">体检项</th><th v-for="year in project.years" :key="year">{{ year }}</th><th>课程出处</th></tr></thead><tbody>
        <tr v-for="row in grouped" :key="row.id"><th class="subject-cell">{{ row.name }}</th><td v-for="year in project.years" :key="year"><template v-if="row.byYear.get(year)"><span class="status-pill" :class="statusClass(row.byYear.get(year)?.status)">{{ row.byYear.get(year)?.status }}</span><small class="table-value" :title="row.byYear.get(year)?.conclusion">{{ formatValue(row.byYear.get(year)) }}</small></template><span v-else class="muted">—</span></td><td class="source-cell">{{ row.source }}</td></tr>
        <tr v-if="!grouped.length"><td :colspan="project.years.length + 2" class="empty-cell">尚无规则结果。</td></tr>
      </tbody></table></div>
      <div class="table-footer"><span>共 {{ grouped.length }} 项规则 · 最新年度 {{ latestYear }}</span><span>不生成单一综合评分，逐项呈现指标状态</span></div>
    </div>
    <div class="result-shortcuts"><button class="shortcut-card" @click="emit('openAuthenticity')"><span class="shortcut-icon">◎</span><span><strong>财务真实性检测</strong><small>查看8项真实性风险信号</small></span><b>→</b></button><button class="shortcut-card" @click="emit('openSteps')"><span class="shortcut-icon">18</span><span><strong>18步详细分析</strong><small>逐步查看指标、阈值与结论</small></span><b>→</b></button></div>
    <div v-if="project.non_financial.status !== 'complete'" class="development-note"><strong>非财务年报信息提取</strong><span>{{ project.non_financial.message }}</span></div>
  </section>
</template>
