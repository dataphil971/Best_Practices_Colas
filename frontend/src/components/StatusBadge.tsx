import type { ItemStatus } from "../types";

const LABELS: Record<ItemStatus, string> = {
  ok: "OK",
  ko: "KO",
  partial: "Partiel",
  na: "N/A",
  unset: "—",
};

export function StatusBadge({ status }: { status: ItemStatus }) {
  return <span className={`status-badge status-badge--${status}`}>{LABELS[status]}</span>;
}
