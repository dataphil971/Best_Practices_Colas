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

/** Où se trouve le constat dans le projet analysé, à la ligne près.
 *  `line` est 1-indexée (comme un éditeur) ; `excerpt` porte le code réel,
 *  seul moyen pour le frontend de montrer la preuve sans jamais accéder au
 *  projet, qui reste sur le poste de l'utilisateur. */
export interface AgentSourceLocation {
  source_file: string;
  line?: number | null;
  end_line?: number | null;
  excerpt?: string | null;
}

export interface AgentFinding {
  rule_id: string;
  object_type: string;
  object: string;
  expected: string;
  actual: unknown;
  status: "OK" | "KO" | "NA";
  evidence: Record<string, unknown>;
  reason: string;
  // Champs d'EXPLICABILITÉ (engine/models.py, Finding) : optionnels ici car
  // toutes les règles ne les renseignent pas encore.
  location?: AgentSourceLocation | null;
  remediation?: string;
  explanation?: string;
}

/** Un CANDIDAT contextuel (engine/models.py, Candidate) : une situation
 *  détectée de façon déterministe que le moteur ne peut pas trancher seul.
 *
 *  Principe repris tel quel du moteur et du skill agent-bi-context-review :
 *  `candidat != violation`. Un candidat ne fait donc JAMAIS basculer
 *  `rule_status` en KO — une règle qui n'émet que des candidats reste `NA`
 *  tant que la revue contextuelle n'a rien qualifié. */
export interface AgentCandidate {
  rule_id: string;
  candidate_id: string;
  candidate_type: string;
  objects: unknown[];
  technical_evidence: Record<string, unknown>;
  review_context: Record<string, unknown>;
}

export interface AgentResult {
  rule_id: string;
  alias?: string;
  rule_name: string;
  execution_status: string;
  rule_status: "OK" | "KO" | "NA";
  findings: AgentFinding[];
  // Absent tant qu'une règle n'émet pas de candidats : le moteur n'expose
  // pas de clé vide, qui laisserait croire qu'une revue est attendue.
  candidates?: AgentCandidate[];
  // Champs spécifiques à chaque règle (ko_details, total_columns, ...).
  [key: string]: unknown;
}

export interface AgentEnvelope {
  schema_version: string;
  engine_version: string;
  // Ajoutés par le schéma 1.1. Optionnels côté type : une enveloppe 1.0
  // produite par un moteur plus ancien reste lisible par ce client.
  generated_at?: string;
  summary?: AgentSummary;
  project: {
    name: string | null;
    format: string | null;
    project_path: string | null;
    semantic_model_path: string | null;
    fingerprint: string | null;
  };
  results: AgentResult[];
}

export interface AgentSummary {
  // Consolidation des statuts de règle : un seul KO suffit à faire KO ;
  // sinon un seul NA suffit à faire NA ; OK exige que toutes concluent OK.
  overall_status: "OK" | "KO" | "NA";
  rules_evaluated: number;
  rules_by_status: Record<"OK" | "KO" | "NA", number>;
  findings_by_status: Record<"OK" | "KO" | "NA", number>;
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
