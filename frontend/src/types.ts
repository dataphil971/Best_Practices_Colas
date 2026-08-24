// Miroir des schémas Pydantic de Backend/pr_review_backend (app/schemas/*.py)
// et du contrat JSON Agent BI (Agent_BI/README_Agent_BI.md, section "Contrat JSON").
// Toute évolution d'un schéma côté backend doit être répercutée ici.

export type ChecklistType = "powerbi" | "appbi" | "build";
export type ReviewStatus =
  | "draft"
  | "in_progress"
  | "submitted"
  | "validated"
  | "changes_requested";
export type ItemStatus = "ok" | "ko" | "partial" | "na" | "unset";
export type ProgressState = "todo" | "in_progress" | "done";
export type Criticality = "blocking" | "recommended" | "optional";
export type UserRole = "user" | "reviewer" | "admin";

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface ReviewSummary {
  id: string;
  report_name: string;
  checklist_type: ChecklistType;
  author_id: string;
  author_name: string | null;
  status: ReviewStatus;
  compliance_score: number | null;
  item_count: number;
  created_at: string;
  submitted_at: string | null;
  validated_at: string | null;
}

export interface ReviewItemOut {
  id: string;
  rule_version_id: string;
  rule_text: string;
  subs: string[];
  criticality: Criticality;
  version_number: number;
  status: ItemStatus;
  progress: ProgressState;
  comment: string;
  risk: string;
  risk_comment: string;
  proposed_solution: string;
  estimated_days: string;
  target_date: string | null;
  definition_of_done: string;
  priority: string;
  responsible: string;
  last_update: string;
  // Provenance Agent BI (Lot 8).
  last_update_source: "unset" | "human" | "agent";
  agent_evidence: Record<string, unknown> | null;
}

export interface CategoryGroup {
  category_id: string | null;
  category_name: string;
  order_index: number;
  items: ReviewItemOut[];
}

export interface ScoreBreakdown {
  score: number;
  ok: number;
  ko: number;
  partial: number;
  na: number;
  unset: number;
  evaluated: number;
  total: number;
}

export interface ReviewDetail {
  id: string;
  report_name: string;
  checklist_type: ChecklistType;
  author_id: string;
  author_name: string | null;
  status: ReviewStatus;
  compliance_score: number | null;
  breakdown: ScoreBreakdown;
  unset_count: number;
  groups: CategoryGroup[];
  created_at: string;
  submitted_at: string | null;
  validated_at: string | null;
}

// --- Agent BI : contrat JSON (Agent_BI/03_PYTHON/engine/envelope.py) -------
export interface AgentFinding {
  rule_id: string;
  object_type: string;
  object: string;
  expected: string;
  actual: unknown;
  status: "OK" | "KO" | "NA";
  evidence: Record<string, unknown>;
  reason: string;
}

export interface AgentResult {
  rule_id: string;
  alias?: string;
  rule_name: string;
  execution_status: string;
  rule_status: "OK" | "KO" | "NA";
  findings: AgentFinding[];
  // Champs spécifiques à chaque règle (ko_details, total_columns, ...).
  [key: string]: unknown;
}

export interface AgentEnvelope {
  schema_version: string;
  engine_version: string;
  project: {
    name: string | null;
    format: string | null;
    project_path: string | null;
    semantic_model_path: string | null;
    fingerprint: string | null;
  };
  results: AgentResult[];
}

// --- Agent BI : résumé d'import (Backend app/schemas/agent_results.py) ----
export interface AgentImportDetail {
  rule_id: string;
  reason?: string;
  previous_status?: string;
  proposed_status?: string;
}

export interface AgentImportResult {
  applied: number;
  conflicts: number;
  unmatched: number;
  already_applied: number;
  total: number;
  details: {
    applied: AgentImportDetail[];
    conflicts: AgentImportDetail[];
    unmatched: AgentImportDetail[];
    already_applied: AgentImportDetail[];
  };
}
