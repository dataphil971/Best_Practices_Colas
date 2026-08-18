"""Assemblage de la vue détaillée d'une revue (Lot 3).

Construit la représentation complète d'une revue : tous les items (y compris
ceux laissés `unset`), groupés par catégorie, chacun enrichi du contenu figé de
sa version de règle (texte, sous-points, criticité). Un reviewer/admin voit ainsi
l'intégralité du périmètre, même ce que l'auteur n'a pas renseigné.
"""
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.review import Review, ReviewItem
from app.models.rule import RuleVersion, Rule
from app.models.category import Category
from app.models.user import User
from app.schemas.review import (
    ReviewDetail,
    ReviewItemOut,
    CategoryGroup,
    ScoreBreakdown,
    ReviewSummary,
)
from app.services.review import compute_score


def _author_name(db: Session, author_id: uuid.UUID) -> str | None:
    u = db.get(User, author_id)
    return u.display_name if u else None


def review_summary(db: Session, review: Review) -> ReviewSummary:
    item_count = db.scalar(
        select(func.count())
        .select_from(ReviewItem)
        .where(ReviewItem.review_id == review.id)
    ) or 0
    out = ReviewSummary.model_validate(review)
    out.author_name = _author_name(db, review.author_id)
    out.item_count = int(item_count)
    return out


def review_detail(db: Session, review: Review) -> ReviewDetail:
    # Charge items + version + règle + catégorie en une passe.
    rows = db.execute(
        select(ReviewItem, RuleVersion, Rule, Category)
        .join(RuleVersion, RuleVersion.id == ReviewItem.rule_version_id)
        .join(Rule, Rule.id == RuleVersion.rule_id)
        .join(Category, Category.id == Rule.category_id)
        .where(ReviewItem.review_id == review.id)
    ).all()

    items_only = [r[0] for r in rows]
    breakdown_dict = compute_score(items_only)

    # Regroupement par catégorie, en conservant l'ordre.
    groups: dict[uuid.UUID, CategoryGroup] = {}
    for item, version, _rule, category in rows:
        grp = groups.get(category.id)
        if grp is None:
            grp = CategoryGroup(
                category_id=category.id,
                category_name=category.name,
                order_index=category.order_index,
                items=[],
            )
            groups[category.id] = grp
        grp.items.append(
            ReviewItemOut(
                id=item.id,
                rule_version_id=item.rule_version_id,
                rule_text=version.text,
                subs=list(version.subs or []),
                criticality=version.criticality,
                version_number=version.version_number,
                status=item.status,
                progress=item.progress,
                comment=item.comment or "",
                risk=item.risk or "",
                risk_comment=item.risk_comment or "",
                proposed_solution=item.proposed_solution or "",
                estimated_days=item.estimated_days or "",
                target_date=item.target_date,
                definition_of_done=item.definition_of_done or "",
                priority=item.priority or "",
                responsible=item.responsible or "",
                last_update=item.last_update,
                last_update_source=item.last_update_source,
                agent_evidence=item.agent_evidence,
            )
        )

    ordered_groups = sorted(
        groups.values(), key=lambda g: (g.order_index, g.category_name)
    )
    for g in ordered_groups:
        g.items.sort(key=lambda i: i.rule_text.lower())

    return ReviewDetail(
        id=review.id,
        report_name=review.report_name,
        checklist_type=review.checklist_type,
        author_id=review.author_id,
        author_name=_author_name(db, review.author_id),
        status=review.status,
        compliance_score=review.compliance_score,
        breakdown=ScoreBreakdown(**breakdown_dict),
        unset_count=breakdown_dict["unset"],
        groups=ordered_groups,
        created_at=review.created_at,
        submitted_at=review.submitted_at,
        validated_at=review.validated_at,
    )
