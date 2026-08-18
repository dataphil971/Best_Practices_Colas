"""
Application des résultats Agent BI à une revue (Lot 8).

Contrairement à l'import Excel (import_runner.py), ce chemin ne dépend
d'aucun fournisseur externe (pas de stockage de fichier, pas de matching
par IA) : le rapprochement règle <-> item est déterministe, via `rules.code`
(ex. "BP-22"). Le traitement est donc synchrone — pas besoin de la
mécanique ImportJob/BackgroundTasks utilisée pour l'Excel.

Invariants respectés (cf. Agent_BI/README_Agent_BI.md et
ALGORITHMIE_AGENT_BI_v1.md, section 9.4 « Conflits ») :

  1. Un item déjà saisi par un humain (`last_update_source == "human"`)
     n'est JAMAIS écrasé silencieusement par un import agent : c'est un
     conflit signalé, pas une application.
  2. Réappliquer le même résultat sur le même état de projet
     (`project.fingerprint` inchangé) est un no-op, pas une réécriture.
  3. Le score de la revue est recalculé UNE SEULE FOIS après le lot complet,
     jamais par item.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ItemStatus
from app.models.review import Review, ReviewItem
from app.models.rule import Rule, RuleVersion
from app.schemas.agent_results import AgentEnvelopeIn
from app.services.review import recompute_and_cache_score

SUPPORTED_SCHEMA_VERSIONS = {"1.0"}

_STATUS_MAP = {
    "OK": ItemStatus.ok,
    "KO": ItemStatus.ko,
    "NA": ItemStatus.na,
}


def apply_agent_envelope(db: Session, *, review: Review, envelope: AgentEnvelopeIn) -> dict:
    """Applique une enveloppe Agent BI à une revue et retourne le résumé
    d'application (compteurs + détail par catégorie)."""
    if envelope.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(
            f"schema_version {envelope.schema_version!r} non supportée "
            f"(supportées : {sorted(SUPPORTED_SCHEMA_VERSIONS)})."
        )

    applied: list[dict] = []
    conflicts: list[dict] = []
    unmatched: list[dict] = []
    already_applied: list[dict] = []
    fingerprint = envelope.project.fingerprint

    for result in envelope.results:
        rule = db.scalar(select(Rule).where(Rule.code == result.rule_id))
        if rule is None:
            unmatched.append({"rule_id": result.rule_id, "reason": "rule_code_unknown"})
            continue

        item = db.scalar(
            select(ReviewItem)
            .join(RuleVersion, RuleVersion.id == ReviewItem.rule_version_id)
            .where(ReviewItem.review_id == review.id, RuleVersion.rule_id == rule.id)
        )
        if item is None:
            unmatched.append({"rule_id": result.rule_id, "reason": "rule_not_in_review_snapshot"})
            continue

        target_status = _STATUS_MAP.get(result.rule_status)
        if target_status is None:
            # Ne devrait jamais arriver (le contrat Agent BI garantit
            # OK/KO/NA) ; on ne fait pas confiance aveuglément pour autant.
            unmatched.append({"rule_id": result.rule_id, "reason": "unexpected_rule_status"})
            continue

        if item.last_update_source == "human":
            conflicts.append({
                "rule_id": result.rule_id,
                "previous_status": item.status.value,
                "proposed_status": target_status.value,
            })
            continue

        if fingerprint and item.agent_fingerprint == fingerprint and item.status == target_status:
            already_applied.append({"rule_id": result.rule_id})
            continue

        item.status = target_status
        item.agent_evidence = result.model_dump()
        item.last_update_source = "agent"
        item.agent_fingerprint = fingerprint
        item.last_update = datetime.now(timezone.utc)
        applied.append({"rule_id": result.rule_id, "proposed_status": target_status.value})

    db.flush()
    recompute_and_cache_score(db, review)

    return {
        "applied": len(applied),
        "conflicts": len(conflicts),
        "unmatched": len(unmatched),
        "already_applied": len(already_applied),
        "total": len(envelope.results),
        "details": {
            "applied": applied,
            "conflicts": conflicts,
            "unmatched": unmatched,
            "already_applied": already_applied,
        },
    }
