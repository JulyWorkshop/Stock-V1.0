export type PageKey = 'import' | 'confirm' | 'overview' | 'authenticity' | 'steps18'
export type StatementType = '合并资产负债表' | '合并利润表' | '合并现金流量表'
export type RuleStatus = '优势' | '一般' | '关注' | '高风险' | '淘汰' | '不适用'

export interface CompanyData {
  name: string
  stock_code: string
  display_name: string
}

export interface ReportData {
  year: number
  file_name: string
  report_title: string
  is_scanned: boolean
  parse_warnings: string[]
}

export interface LineItemData {
  year: number
  statement_type: StatementType
  name: string
  aliases: string[]
  original_value: number | null
  modified_value: number | null
  value: number | null
  unit: string
  source_pdf: string
  source_page: number
  is_recognized: boolean
  is_modified: boolean
}

export interface EvidenceData {
  year: number
  statement_type: string
  name: string
  value: number | null
  unit: string
  source_pdf: string
  source_page: number
  is_recognized: boolean
}

export interface RuleResultData {
  rule_id: string
  rule_name: string
  year: number
  actual_value: number | Record<string, unknown> | null
  reference_value: string
  status: RuleStatus
  conclusion: string
  evidence: EvidenceData[]
  course_source: string
  is_calculable: boolean
  step: number
}

export interface RuleMetaData {
  id: string
  name: string
  step: number
  thresholds: Record<string, unknown>
  description: string
  course_source: string
}

export interface ImportMessage {
  code: string
  message: string
  file: string
  year?: number | null
}

export interface AnalysisProjectData {
  company: CompanyData
  years: number[]
  reports: ReportData[]
  line_items: LineItemData[]
  standard_subjects: Record<StatementType, string[]>
  rule_results: RuleResultData[]
  rules: RuleMetaData[]
  errors: ImportMessage[]
  warnings: ImportMessage[]
  non_financial: {
    status: 'not_started' | 'in_progress' | 'complete' | 'partial'
    message: string
    sections: Array<{ title: string; status: string; extracted_items: string[] }>
  }
}
