export type CriterionStatus = 'met' | 'partially_met' | 'missing' | 'not_applicable';
export type Severity = 'critical' | 'major' | 'minor';
export type Priority = 'critical' | 'high' | 'medium' | 'low';

export interface DocumentClassification {
  doc_type: string;
  branch: string;
  label: string;
  purpose: string;
  court_or_authority: string | null;
  procedural_stage: string | null;
  summary: string;
  confidence: 'high' | 'medium' | 'low';
}

export interface CriterionReport {
  criterion_id: string;
  category: string;
  category_label: string;
  text: string;
  critical: boolean;
  weight: number;
  status: CriterionStatus;
  score: number;
  evidence: string | null;
  commentary: string;
}

export interface CategoryScore {
  category: string;
  label: string;
  weight: number;
  score: number | null;
  criteria_count: number;
}

export interface ScoreSummary {
  overall: number;
  verdict: string;
  verdict_detail: string;
  capped: boolean;
  cap_reason: string | null;
  categories: CategoryScore[];
}

export interface ExtraFinding {
  title: string;
  severity: Severity;
  commentary: string;
}

export interface Suggestion {
  priority: Priority;
  target: string;
  proposed_action: string;
  rationale: string;
}

export interface AuditorInfo {
  branch: string;
  title: string;
  description: string;
}

export interface AuditReport {
  classification: DocumentClassification;
  auditor: AuditorInfo;
  score: ScoreSummary;
  criteria: CriterionReport[];
  extra_findings: ExtraFinding[];
  suggestions: Suggestion[];
  overall_assessment: string;
  model: string;
}

export interface DocumentTypeInfo {
  key: string;
  label: string;
  branch: string;
  description: string;
}

export type PipelineStage =
  | { stage: 'classifying'; data: null }
  | { stage: 'classified'; data: DocumentClassification }
  | { stage: 'auditing'; data: { criteria_count: number; auditor: AuditorInfo } }
  | { stage: 'complete'; data: AuditReport }
  | { stage: 'error'; data: { detail: string; code: string } };
