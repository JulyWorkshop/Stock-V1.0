<script setup lang="ts">
import { computed } from 'vue'
import type { AnalysisProjectData, RuleResultData } from '../types'

const props = defineProps<{ project: AnalysisProjectData; busy: boolean }>()
const emit = defineEmits<{ recalculate: [] }>()
const framework = [
  '行业地位与公司基本面', '管理层与股权结构', '总资产规模与成长性', '偿债风险分析',
  '竞争优势（应付预收－应收预付）', '应收/合同资产占比', '固定资产占比（重资产/轻资产）',
  '投资类资产占比（主业专注度）', '存货商誉爆雷风险', '营收增长率', '毛利率（核心竞争力）',
  '期间费用率/毛利率', '销售费用率', '主营利润率', '5年平均净现比（造血能力）',
  'ROE（净资产收益率）', '资本开支/经营现金流（扩张能力）', '分红/经营现金流（分红意愿）',
]
const stepRows = computed(() => framework.map((title, index) => {
  const step = index + 1
  const results = props.project.rule_results.filter((item) => item.step === step).sort((a, b) => a.year - b.year)
  const meta = props.project.rules.find((rule) => rule.step === step)
  return { step, title, results, source: meta?.course_source || '', threshold: meta?.description || '' }
}))
const latestYear = computed(() => props.project.years[props.project.years.length - 1])
const covered = computed(() => stepRows.value.filter((row) => row.results.some((item) => item.year === latestYear.value)).length)
function formatValue(result: RuleResultData) {
  if (result.actual_value === null) return '—'
  if (typeof result.actual_value === 'object') return Object.entries(result.actual_value).filter(([key]) => key !== 'total_assets').map(([key, value]) => `${key}=${typeof value === 'number' ? `${(value * 100).toFixed(2)}%` : value}`).join(' / ')
  const id = result.rule_id
  const isRatio = /ratio|margin|roe|growth|yield/.test(id) || id.endsWith('_cash_ratio')
  return isRatio ? `${(result.actual_value * 100).toFixed(2)}%` : Number(result.actual_value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function statusClass(status: string) { return `status-${status.replaceAll('/', '-')}` }
</script>

<template>
  <section class="page-content">
    <div class="page-heading"><div><div class="eyebrow">STEP 05 · 18-STEP FRAMEWORK</div><h1>18 步详细分析</h1><p>按照原软件18步框架逐项展示年度指标、参考阈值、判断状态和计算结论。</p></div><button class="button button-outline" :disabled="busy" @click="emit('recalculate')">↻ 重新计算</button></div>
    <div class="company-banner compact"><div class="company-avatar">{{ project.company.name.slice(0, 1) || '企' }}</div><div class="company-main"><strong>{{ project.company.display_name }}</strong><span>{{ project.years[0] }}—{{ latestYear }} · 最新年度 {{ latestYear }}</span></div><div class="company-meta"><span>已覆盖步骤</span><strong>{{ covered }}/18</strong></div></div>
    <div class="steps-summary"><div><strong>{{ covered }} / 18</strong><span>最新年度有规则结果的步骤</span></div><div class="steps-progress"><i :style="{ width: `${covered / 18 * 100}%` }"></i></div><small>第1、2步当前尚无自动计算规则；其余步骤按规则文件实际覆盖情况展示。</small></div>
    <div class="steps-list">
      <article v-for="row in stepRows" :key="row.step" class="panel step-card">
        <div class="step-card-heading"><div class="step-index">{{ String(row.step).padStart(2, '0') }}</div><div class="step-title"><h2>第{{ row.step }}步：{{ row.title }}</h2><p>{{ row.source || '课程出处待补充' }}</p></div><span class="step-count">{{ row.results.length ? `${row.results.length} 条年度结果` : '待实现 / 无规则' }}</span></div>
        <div v-if="row.threshold" class="threshold-line"><strong>参考标准：</strong>{{ row.threshold }}</div>
        <div v-if="row.results.length" class="step-results">
          <div v-for="result in row.results" :key="`${result.rule_id}-${result.year}`" class="step-result-row">
            <span class="step-year">{{ result.year }}</span><strong class="step-rule-name">{{ result.rule_name }}</strong><span class="step-value">{{ formatValue(result) }}</span><span class="status-pill" :class="statusClass(result.status)">{{ result.status }}</span><p>{{ result.conclusion }}</p>
            <details v-if="result.evidence.length" class="evidence-details"><summary>查看计算依据与年报来源（{{ result.evidence.length }} 项）</summary><div v-for="(item, i) in result.evidence" :key="i" class="evidence-item"><span>{{ item.name }}</span><strong>{{ item.value ?? 0 }} {{ item.unit }}</strong><small>{{ item.source_pdf || '来源文件未记录' }} · 第 {{ item.source_page || '—' }} 页</small></div></details>
          </div>
        </div>
        <div v-else class="step-not-implemented">此步骤目前没有自动计算规则或结果。按照原软件现状如实显示，不使用模拟数据。</div>
      </article>
    </div>
  </section>
</template>
