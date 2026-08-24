import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createReview } from "../api/reviews";
import type { ChecklistType } from "../types";

export function NewReviewPage() {
  const navigate = useNavigate();
  const [reportName, setReportName] = useState("");
  const [checklistType, setChecklistType] = useState<ChecklistType>("powerbi");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const review = await createReview(reportName, checklistType);
      navigate(`/reviews/${review.id}`);
    } catch {
      setError("Impossible de créer la revue.");
      setIsSubmitting(false);
    }
  }

  return (
    <form className="new-review-form" onSubmit={(e) => void onSubmit(e)}>
      <h1>Nouvelle revue</h1>
      <label>
        Nom du rapport
        <input value={reportName} onChange={(e) => setReportName(e.target.value)} required />
      </label>
      <label>
        Référentiel
        <select
          value={checklistType}
          onChange={(e) => setChecklistType(e.target.value as ChecklistType)}
        >
          <option value="powerbi">Power BI</option>
          <option value="appbi">App BI</option>
          <option value="build">Build</option>
        </select>
      </label>
      {error && <p className="error-text">{error}</p>}
      <button type="submit" disabled={isSubmitting}>
        Créer
      </button>
    </form>
  );
}
