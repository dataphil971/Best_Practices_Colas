"""Assemblage des objets de sortie du référentiel (règle + catégorie + version)."""
from sqlalchemy.orm import Session

from app.models.rule import Rule, RuleVersion
from app.models.rule_activity import RuleActivity
from app.models.category import Category
from app.models.user import User
from app.schemas.referential import RuleOut, RuleVersionOut, RuleActivityOut
from app.services.referential import get_current_version


def rule_to_out(
    db: Session, rule: Rule, *, category_name: str | None = None
) -> RuleOut:
    """Construit la représentation d'une règle avec sa version courante."""
    if category_name is None:
        cat = db.get(Category, rule.category_id)
        category_name = cat.name if cat else ""

    current = get_current_version(db, rule.id)
    return RuleOut(
        id=rule.id,
        checklist_type=rule.checklist_type,
        category_id=rule.category_id,
        category_name=category_name,
        status=rule.status,
        current_version=(
            RuleVersionOut.model_validate(current) if current else None
        ),
        created_at=rule.created_at,
    )


def activity_to_out(db: Session, entry: RuleActivity) -> RuleActivityOut:
    """Enrichit une entrée de journal avec le nom lisible de l'acteur."""
    actor = db.get(User, entry.actor_id)
    out = RuleActivityOut.model_validate(entry)
    out.actor_name = actor.display_name if actor else None
    return out
