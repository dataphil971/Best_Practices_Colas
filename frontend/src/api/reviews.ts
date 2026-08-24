import { apiFetch } from "./client";
import type {
  AgentEnvelope,
  AgentImportResult,
  ChecklistType,
  ItemStatus,
  ProgressState,
  ReviewDetail,
  ReviewSummary,
} from "../types";

export function listReviews(
  params: { q?: string; status?: string; type?: string } = {},
): Promise<ReviewSummary[]> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.status) search.set("status_filter", params.status);
  if (params.type) search.set("type", params.type);
  const qs = search.toString();
  return apiFetch<ReviewSummary[]>(`/reviews${qs ? `?${qs}` : ""}`);
}

export function getReview(id: string): Promise<ReviewDetail> {
  return apiFetch<ReviewDetail>(`/reviews/${id}`);
}

export function createReview(
  report_name: string,
  checklist_type: ChecklistType,
): Promise<ReviewDetail> {
  return apiFetch<ReviewDetail>("/reviews", {
    method: "POST",
    body: { report_name, checklist_type },
  });
}

export interface ReviewItemPatch {
  status?: ItemStatus;
  progress?: ProgressState;
  comment?: string;
  risk?: string;
  risk_comment?: string;
  proposed_solution?: string;
  estimated_days?: string;
  target_date?: string | null;
  definition_of_done?: string;
  priority?: string;
  responsible?: string;
}

export function updateReviewItem(
  reviewId: string,
  itemId: string,
  patch: ReviewItemPatch,
) {
  return apiFetch(`/reviews/${reviewId}/items/${itemId}`, {
    method: "PATCH",
    body: patch,
  });
}

export function submitAgentResults(
  reviewId: string,
  envelope: AgentEnvelope,
): Promise<AgentImportResult> {
  return apiFetch<AgentImportResult>(`/reviews/${reviewId}/agent-results`, {
    method: "POST",
    body: envelope,
  });
}
