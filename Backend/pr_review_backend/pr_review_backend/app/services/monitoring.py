"""
Service de monitoring (Lot 7, §5.6).

Agrégats de pilotage :
  - PORTEFEUILLE : nombre de revues, répartition par statut, score moyen, nombre
    de points bloquants ouverts, avancement global des remédiations — filtrables
    par type de checklist et par statut.
  - DÉTAIL d'une revue : avancement par catégorie et par remédiation (todo / in
    progress / done), points bloquants restants.

La visibilité respecte les règles des lots précédents : un non-admin ne voit que
ses revues et celles qui lui sont partagées.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    UserRole,
    ChecklistType,
    ReviewStatus,
    ItemStatus,
    Criticality,
)
from app.models.user import User
from app.models.review import Review, ReviewItem
from app.models.rule import RuleVersion


def _visible_reviews_query(db: Session, user: User):
    query = select(Review)
    if user.role != UserRole.admin:
        from app.services.validation import list_visible_review_ids_for_reviewer

        shared = list_visible_review_ids_for_reviewer(db, user)
        if shared:
            query = query.where(
                (Review.author_id == user.id) | (Review.id.in_(shared))
            )
        else:
            query = query.where(Review.author_id == user.id)
    return query


def portfolio(
    db: Session,
    *,
    user: User,
    checklist_type: str | None = None,
    status_filter: str | None = None,
) -> dict:
    """Agrégats portefeuille filtrables."""
    query = _visible_reviews_query(db, user)
    if checklist_type:
        try:
            query = query.where(Review.checklist_type == ChecklistType(checklist_type))
        except ValueError:
            pass
    if status_filter:
        try:
            query = query.where(Review.status == ReviewStatus(status_filter))
        except ValueError:
            pass

    reviews = db.scalars(query).all()
    review_ids = [r.id for r in reviews]

    by_status: dict[str, int] = {}
    score_sum = 0
    scored = 0
    for r in reviews:
        by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        if r.compliance_score is not None:
            score_sum += r.compliance_score
            scored += 1

    avg_score = round(score_sum / scored) if scored else None

    # Points bloquants ouverts (criticité blocking, statut KO) sur revues visibles.
    blocking_open = 0
    remediation = {"todo": 0, "in_progress": 0, "done": 0}
    if review_ids:
        rows = db.execute(
            select(ReviewItem, RuleVersion.criticality)
            .join(RuleVersion, RuleVersion.id == ReviewItem.rule_version_id)
            .where(ReviewItem.review_id.in_(review_ids))
        ).all()
        for item, criticality in rows:
            if item.status == ItemStatus.ko and criticality == Criticality.blocking:
                blocking_open += 1
            # Avancement des remédiations : uniquement pour les items KO/Partiel.
            if item.status in (ItemStatus.ko, ItemStatus.partial):
                remediation[item.progress.value] = remediation.get(item.progress.value, 0) + 1

    total_remediation = sum(remediation.values())
    completion = (
        round(remediation["done"] / total_remediation * 100) if total_remediation else None
    )

    return {
        "total_reviews": len(reviews),
        "by_status": by_status,
        "average_score": avg_score,
        "blocking_open": blocking_open,
        "remediation": remediation,
        "remediation_completion": completion,
    }


def review_progress(db: Session, *, review: Review) -> dict:
    """Détail d'avancement d'une revue : par catégorie et par remédiation."""
    from app.models.rule import Rule
    from app.models.category import Category

    rows = db.execute(
        select(ReviewItem, RuleVersion, Rule, Category)
        .join(RuleVersion, RuleVersion.id == ReviewItem.rule_version_id)
        .join(Rule, Rule.id == RuleVersion.rule_id)
        .join(Category, Category.id == Rule.category_id)
        .where(ReviewItem.review_id == review.id)
    ).all()

    categories: dict[uuid.UUID, dict] = {}
    remediation = {"todo": 0, "in_progress": 0, "done": 0}
    blocking_open = 0

    for item, version, _rule, category in rows:
        grp = categories.setdefault(
            category.id,
            {
                "category_name": category.name,
                "order_index": category.order_index,
                "ok": 0, "ko": 0, "partial": 0, "na": 0, "unset": 0,
            },
        )
        grp[item.status.value] = grp.get(item.status.value, 0) + 1

        if item.status in (ItemStatus.ko, ItemStatus.partial):
            remediation[item.progress.value] = remediation.get(item.progress.value, 0) + 1
        if item.status == ItemStatus.ko and version.criticality == Criticality.blocking:
            blocking_open += 1

    ordered = sorted(categories.values(), key=lambda c: (c["order_index"], c["category_name"]))
    total_remediation = sum(remediation.values())
    completion = (
        round(remediation["done"] / total_remediation * 100) if total_remediation else None
    )

    return {
        "review_id": str(review.id),
        "report_name": review.report_name,
        "status": review.status.value,
        "compliance_score": review.compliance_score,
        "blocking_open": blocking_open,
        "by_category": ordered,
        "remediation": remediation,
        "remediation_completion": completion,
    }
