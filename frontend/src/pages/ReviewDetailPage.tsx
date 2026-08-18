import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getReview, updateReviewItem } from "../api/reviews";
import type { ItemStatus } from "../types";
import { AgentConnectPanel } from "../components/AgentConnectPanel";
import { StatusBadge } from "../components/StatusBadge";
import { ScoreBadge } from "../components/ScoreBadge";

const STATUS_OPTIONS: ItemStatus[] = ["unset", "ok", "ko", "partial", "na"];

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const {
    data: review,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["review", id],
    queryFn: () => getReview(id as string),
    enabled: !!id,
  });

  const statusMutation = useMutation({
    mutationFn: ({ itemId, status }: { itemId: string; status: ItemStatus }) =>
      updateReviewItem(id as string, itemId, { status }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["review", id] }),
  });

  if (isLoading) return <p>Chargement…</p>;
  if (error || !review) return <p className="error-text">Revue introuvable.</p>;

  return (
    <div className="review-detail">
      <div className="page-header">
        <div>
          <h1>{review.report_name}</h1>
          <p className="review-meta">
            {review.checklist_type} · {review.status}
          </p>
        </div>
        <ScoreBadge score={review.compliance_score} />
      </div>

      {review.checklist_type === "powerbi" && <AgentConnectPanel reviewId={review.id} />}

      {review.groups.map((group) => (
        <section key={group.category_id ?? group.category_name} className="category-group">
          <h2>{group.category_name}</h2>
          <ul className="item-list">
            {group.items.map((item) => (
              <li key={item.id} className="item-row">
                <div className="item-text">
                  <p>{item.rule_text}</p>
                  {item.last_update_source === "agent" && (
                    <span className="agent-badge" title="Statut appliqué par Agent BI">
                      🤖 Agent BI
                    </span>
                  )}
                </div>
                <select
                  value={item.status}
                  onChange={(e) =>
                    statusMutation.mutate({
                      itemId: item.id,
                      status: e.target.value as ItemStatus,
                    })
                  }
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <StatusBadge status={item.status} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
