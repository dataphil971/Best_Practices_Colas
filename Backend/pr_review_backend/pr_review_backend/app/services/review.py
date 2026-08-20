"""
Service de gestion des revues (Lot 3).

Concentre les invariants métier des revues :

  1. SNAPSHOT à la création : on fige un `review_item` par règle active dont la
     version courante est approuvée, en pointant vers le `rule_version_id` exact.
     Le référentiel peut ensuite évoluer sans jamais altérer une revue passée.

  2. SCORE DE CONFORMITÉ (formule héritée du prototype) :
        évalués      = ok + ko + partial          (na et unset EXCLUS)
        score        = round((ok + 0.5*partial) / évalués * 100)   ou 0 si évalués = 0
     Le score est recalculé et mis en cache sur la revue à chaque màj d'item.

  3. TRANSITIONS de statut contrôlées (draft/in_progress → submitted → validated
     | changes_requested), avec horodatage de soumission.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    ChecklistType,
    ItemStatus,
    ReviewStatus,
)
from app.models.rule import Rule, RuleVersion
from app.models.enums import LifecycleState
from app.models.review import Review, ReviewItem
from app.models.user import User


# --------------------------------------------------------------------------
# Score de conformité
# --------------------------------------------------------------------------
def compute_score(items: list[ReviewItem]) -> dict:
    """
    Calcule le score et la ventilation des statuts d'une liste d'items.

    Retourne un dict : score, ok, ko, partial, na, unset, evaluated, total.
    """
    ok = ko = partial = na = unset = 0
    for it in items:
        if it.status == ItemStatus.ok:
            ok += 1
        elif it.status == ItemStatus.ko:
            ko += 1
        elif it.status == ItemStatus.partial:
            partial += 1
        elif it.status == ItemStatus.na:
            na += 1
        else:
            unset += 1

    evaluated = ok + ko + partial
    score = 0 if evaluated == 0 else round((ok + 0.5 * partial) / evaluated * 100)
    return {
        "score": score,
        "ok": ok,
        "ko": ko,
        "partial": partial,
        "na": na,
        "unset": unset,
        "evaluated": evaluated,
        "total": len(items),
    }


def recompute_and_cache_score(db: Session, review: Review) -> int:
    """Recalcule le score depuis les items en base et le met en cache."""
    items = db.scalars(
        select(ReviewItem).where(ReviewItem.review_id == review.id)
    ).all()
    score = compute_score(list(items))["score"]
    review.compliance_score = score
    return score


# --------------------------------------------------------------------------
# Création avec snapshot
# --------------------------------------------------------------------------
def _current_approved_versions(
    db: Session, checklist_type: ChecklistType
) -> list[RuleVersion]:
    """Versions courantes approuvées des règles ACTIVES d'un référentiel."""
    return list(
        db.scalars(
            select(RuleVersion)
            .join(Rule, Rule.id == RuleVersion.rule_id)
            .where(
                Rule.checklist_type == checklist_type,
                Rule.status == "active",
                RuleVersion.is_current.is_(True),
                RuleVersion.lifecycle == LifecycleState.approved,
            )
        ).all()
    )


def create_review(
    db: Session,
    *,
    author: User,
    report_name: str,
    checklist_type: ChecklistType,
) -> Review:
    """
    Crée une revue et fige son snapshot : un item par règle active du référentiel,
    pointant vers la version courante approuvée.
    """
    review = Review(
        report_name=report_name,
        checklist_type=checklist_type,
        author_id=author.id,
        status=ReviewStatus.in_progress,
        compliance_score=0,
    )
    db.add(review)
    db.flush()

    versions = _current_approved_versions(db, checklist_type)
    for v in versions:
        db.add(ReviewItem(review_id=review.id, rule_version_id=v.id))
    db.flush()
    return review


# --------------------------------------------------------------------------
# Mise à jour d'un item
# --------------------------------------------------------------------------
# Champs de l'item modifiables par l'auteur (bloc statut + remédiation).
_EDITABLE_ITEM_FIELDS = {
    "status",
    "progress",
    "comment",
    "risk",
    "risk_comment",
    "proposed_solution",
    "estimated_days",
    "target_date",
    "definition_of_done",
    "priority",
    "responsible",
}

# Seuls champs éditables dont la colonne est NULLABLE : eux seuls acceptent un
# `null` explicite (c'est ainsi que le client efface une échéance). Pour les
# autres, un `null` reçu serait une violation NOT NULL — on l'ignore.
_NULLABLE_ITEM_FIELDS = {"target_date"}


def update_item(
    db: Session, *, review: Review, item: ReviewItem, patch: dict
) -> ReviewItem:
    """
    Applique une mise à jour partielle à un item puis recalcule le score.

    Seuls les champs autorisés sont pris en compte ; les clés inconnues sont
    ignorées silencieusement (le schéma Pydantic les a déjà filtrées en amont).

    `patch` provient d'un `model_dump(exclude_unset=True)` : une clé présente
    signifie donc « le client a explicitement envoyé cette valeur ». Un `null`
    sur un champ nullable est une demande d'effacement, pas une absence.
    """
    for field, value in patch.items():
        if field not in _EDITABLE_ITEM_FIELDS:
            continue
        if value is None and field not in _NULLABLE_ITEM_FIELDS:
            continue
        setattr(item, field, value)
    if "status" in patch and patch["status"] is not None:
        # Une saisie humaine du statut reprend toujours la main sur un
        # éventuel import agent précédent (cf. agent_results.py).
        item.last_update_source = "human"
    db.flush()
    recompute_and_cache_score(db, review)
    return item


# --------------------------------------------------------------------------
# Transitions de statut
# --------------------------------------------------------------------------
def set_status(db: Session, *, review: Review, new_status: ReviewStatus) -> Review:
    """
    Change le statut d'une revue en horodatant la soumission le cas échéant.

    La validation/refus par un tiers relèvera du Lot 4 ; ici on autorise l'auteur
    à repasser en cours ou à soumettre.
    """
    review.status = new_status
    if new_status == ReviewStatus.submitted and review.submitted_at is None:
        review.submitted_at = datetime.now(timezone.utc)
    db.flush()
    return review
