<script setup lang="ts">
import { computed } from 'vue'
import type { AnalysisProjectData, RuleResultData } from '../types'

const props = defineProps<{ project: AnalysisProjectData; busy: boolean }>()
const emit = defineEmits<{ recalculate: [] }>()
const ruleIds = [
  'auth_cash_interest_yield',
  'auth_prepayment_ratio',
  'auth_prepay_other_receivable',
  'auth_cash_receipt_ratio',
  'auth_net_profit_cash_ratio',
  'auth_cash_interest_debt_combo',
  'auth_fixed_assets_growth',
  'auth_gross_margin_volatility',
]
const ruleRows = computed(() => ruleIds.map((id) => {
  const results = props.project.rule_results.filter((item) => item.rule_id === id)
  return { id, name: results[0]?.rule_name || props.project.rules.find((rule) => rule.id === id)?.name || id, source: results[0]?.course_source || '', byYear: new Map<number, RuleResultData>(results.map((item) => [item.year, item] as const)) }
}))
const latestYear = computed(() => props.project.years[props.project.years.length - 1])
const latestResults = computed(() => props.project.rule_results.filter((item) => item.year === latestYear.value && ruleIds.includes(item.rule_id)))
const highCount = computed(() => latestResults.value.filter((item) => ['高风险', '淘汰'].includes(item.status)).length)
const attentionCount = computed(() => latestResults.value.filter((item) => item.status === '关注').length)
const riskText = computed(() => highCount.value ? '存在高风险信号' : attentionCount.value ? '存在需要关注的信号' : '未发现明显高风险信号')
function formatValue(result?: RuleResultData) {
  if (!result) return '—'
  if (typeof result.actual_value === 'number') return `${(result.actual_value * 100).toFixed(2)}%`
  if (result.actual_value && typeof result.actual_value === 'object') return JSON.stringify(result.actual_value)
  return result.conclusion || '—'
}
function statusText(status?: string) {
  if (status === '优势' || status === '一般') return '正常'
  return status || '—'
}
function statusClass(status?: string) { return `status-${(status || '不适用').replaceAll('/', '-')}` }
</script>

<template>
  <section class="page-content">
    <div class="page-heading"><div><div class="eyebrow">STEP 04 · FINANCIAL AUTHENTICITY</div><h1>财务真实性检测</h1><p>通过关键财务信号识别需要进一步核实的异常，不将单一风险信号直接等同于财务造假。</p></div><button class="button button-outline" :disabled="busy" @click="emit('recalculate')">↻ 重新计算</button></div>
    <div class="company-banner compact"><div class="company-avatar">{{ project.company.name.slice(0, 1) || '企' }}</div><div class="company-main"><strong>{{ project.company.display_name }}</strong><span>{{ project.years[0] }}—{{ latestYear }} · {{ project.years.length }} 个年度</span></div></div>
    <div class="auth-explainer"><strong>检测说明</strong><p>重点观察现金利息收益率、预付款项、其他应收款、收现比、净现比，以及货币资金与有息负债组合、固定资产短期增长和毛利率波动。异常项目应结合年报附注、审计意见和经营情况进一步核实。</p></div>
    <div class="risk-overview" :class="highCount ? 'risk-high' : attentionCount ? 'risk-attention' : 'risk-low'"><div><span>最新年度（{{ latestYear }}）检测概况</span><strong>{{ riskText }}</strong></div><div class="risk-counts"><span>高风险 / 淘汰 <b>{{ highCount }}</b></span><span>关注 <b>{{ attentionCount }}</b></span><span>检测项 <b>{{ latestResults.length }}/8</b></span></div></div>
    <div class="panel table-panel"><div class="panel-heading"><div><h2>真实性检测结果矩阵</h2><p>显示各年度检测状态和实际指标值，点击结论可查看证据。</p></div><span class="subtle-count">8 项检测</span></div>
      <div class="table-scroll"><table class="data-table overview-table"><thead><tr><th class="subject-col">检测项</th><th v-for="year in project.years" :key="year">{{ year }}</th><th>课程出处</th></tr></thead><tbody>
        <tr v-for="row in ruleRows" :key="row.id"><th class="subject-cell">{{ row.name }}</th><td v-for="year in project.years" :key="year"><template v-if="row.byYear.get(year)"><span class="status-pill" :class="statusClass(row.byYear.get(year)?.status)">{{ statusText(row.byYear.get(year)?.status) }}</span><small class="table-value" :title="row.byYear.get(year)?.conclusion">{{ formatValue(row.byYear.get(year)) }}</small></template><span v-else class="muted">—</span></td><td class="source-cell">{{ row.source }}</td></tr>
      </tbody></table></div>
      <div class="table-footer"><span>数据年度 {{ project.years.length }} 年 · 规则结果 {{ latestResults.length }} 项</span><span>风险信号仅用于提示，不构成造假事实认定</span></div>
    </div>
    <div class="panel detail-panel"><h2>最新年度需要进一步核实的项目</h2><div v-if="latestResults.filter((item) => ['关注', '高风险', '淘汰'].includes(item.status)).length" class="evidence-list"><div v-for="item in latestResults.filter((item) => ['关注', '高风险', '淘汰'].includes(item.status))" :key="item.rule_id" class="evidence-row"><span class="status-pill" :class="statusClass(item.status)">{{ item.status }}</span><div><strong>{{ item.rule_name }}</strong><p>{{ item.conclusion }}</p></div></div></div><p v-else class="empty-copy">最新年度没有需要进一步核实的异常信号。仍建议结合审计意见、附注及经营情况综合判断。</p></div>
  </section>
</template>
