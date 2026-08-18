import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listReviews } from "../api/reviews";
import { ScoreBadge } from "../components/ScoreBadge";

export function ReviewListPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["reviews"],
    queryFn: () => listReviews(),
  });

  if (isLoading) return <p>Chargement des revues…</p>;
  if (error) return <p className="error-text">Impossible de charger les revues.</p>;

  return (
    <div>
      <div className="page-header">
        <h1>Mes revues</h1>
        <Link className="btn-primary" to="/reviews/new">
          Nouvelle revue
        </Link>
      </div>
      {data && data.length === 0 && <p>Aucune revue pour l'instant.</p>}
      <ul className="review-list">
        {data?.map((r) => (
          <li key={r.id}>
            <Link to={`/reviews/${r.id}`} className="review-row">
              <span className="review-name">{r.report_name}</span>
              <span className="review-type">{r.checklist_type}</span>
              <span className="review-status">{r.status}</span>
              <ScoreBadge score={r.compliance_score} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
