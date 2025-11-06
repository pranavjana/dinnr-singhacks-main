/**
 * Type definitions for compliance rules and extraction API responses
 */

export type ValidationStatus = 'pending' | 'validated' | 'rejected' | 'archived'

export type ExtractionStatus = 'completed' | 'partial' | 'failed'

export interface ComplianceRule {
  id: string
  rule_type: string
  description?: string
  jurisdiction: string
  regulator: string
  applies_to: string[]
  rule_details: Record<string, unknown>
  source_text: string
  extraction_confidence: number
  effective_date?: string
  circular_number?: string
  validation_status: ValidationStatus
  created_at?: string
  updated_at?: string
}

export interface ExtractionResponse {
  workflow_run_id: string
  document_id: string
  status: ExtractionStatus
  rules_created: number
  rules_updated: number
  avg_confidence: number
  total_tokens_used: number
  cost_usd: number
  errors: string[]
  deduplication_summary?: Record<string, any>
}

export interface BatchExtractionResponse {
  total_documents: number
  successful: number
  failed: number
  results: ExtractionResponse[]
}

export interface ComplianceRulesResponse {
  count: number
  rules: ComplianceRule[]
}

export interface ExtractionMetric {
  id: string
  workflow_run_id: string
  document_id: string
  total_chunks_processed: number
  rules_extracted: number
  avg_confidence_score: number
  total_tokens_used: number
  total_cost_usd: number
  processing_time_seconds: number
  created_at: string
}

export interface ExtractionMetricsResponse {
  count: number
  metrics: ExtractionMetric[]
}

export interface ComplianceRuleCreatePayload {
  rule_type: string
  jurisdiction: string
  regulator?: string
  description?: string
  source_text: string
  applies_to: string[]
  rule_details: Record<string, unknown>
  extraction_confidence: number
  effective_date?: string
  circular_number?: string
  validation_status?: ValidationStatus
  is_active?: boolean
}

export type ComplianceRuleUpdatePayload = Partial<ComplianceRuleCreatePayload> & {
  rule_details?: Record<string, unknown>
  applies_to?: string[]
}
