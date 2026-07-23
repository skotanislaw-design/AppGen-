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
  firm_standard: AuthenticityVerdict | null;
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

export type TellType = 'structure' | 'phrasing' | 'rhythm' | 'register' | 'citation' | 'other';
export type AuthenticityVerdict = 'human_register' | 'borderline' | 'ai_marked';

export interface AITellFinding {
  tell_type: TellType;
  quote: string;
  explanation: string;
  rewrite: string | null;
}

export interface ExemplaryGap {
  aspect: string;
  gap: string;
  proposed_action: string;
}

export interface FirmStandardReview {
  authenticity_verdict: AuthenticityVerdict;
  register_score: number;
  ai_tell_findings: AITellFinding[];
  exemplary_gaps: ExemplaryGap[];
  assessment: string;
}

export interface AuditReport {
  classification: DocumentClassification;
  auditor: AuditorInfo;
  score: ScoreSummary;
  criteria: CriterionReport[];
  extra_findings: ExtraFinding[];
  suggestions: Suggestion[];
  firm_standard: FirmStandardReview;
  overall_assessment: string;
  model: string;
}

export interface DocumentTypeInfo {
  key: string;
  label: string;
  branch: string;
  description: string;
}

export interface ExemplarSummary {
  doc_type: string;
  doc_type_label: string;
  branch: string;
  title: string;
  scenario: string;
}

export interface ExemplarDetail extends ExemplarSummary {
  body: string;
  drafting_notes: string[];
  key_provisions: string[];
}

export type PipelineStage =
  | { stage: 'classifying'; data: null }
  | { stage: 'classified'; data: DocumentClassification }
  | { stage: 'auditing'; data: { criteria_count: number; auditor: AuditorInfo } }
  | { stage: 'firm_review'; data: null }
  | { stage: 'complete'; data: AuditReport }
  | { stage: 'error'; data: { detail: string; code: string } };
