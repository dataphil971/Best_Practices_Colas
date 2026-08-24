export function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) {
    return <span className="score-badge score-badge--empty">—</span>;
  }
  const level = score >= 80 ? "good" : score >= 50 ? "mid" : "bad";
  return <span className={`score-badge score-badge--${level}`}>{score}%</span>;
}
