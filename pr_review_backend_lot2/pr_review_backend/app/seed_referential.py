"""
Import initial du référentiel (Lot 2).

Charge le référentiel de base (issu des templates v2 et v3 du prototype) dans la
base : catégories, règles et leur version 1 (approuvée, courante). Chaque import
est tracé dans le journal d'activité au nom d'un administrateur « système ».

Idempotent : une catégorie déjà présente (même `checklist_type` + `name`) n'est
pas recréée, et une règle dont le libellé existe déjà dans la catégorie n'est pas
dupliquée. On peut donc relancer le seed sans risque.

Usage :
    python -m app.seed_referential                 # admin système auto
    python -m app.seed_referential --actor <email> # attribuer à un admin réel
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.enums import ChecklistType, Criticality, LifecycleState, UserRole
from app.models.user import User
from app.models.category import Category
from app.models.rule import Rule, RuleVersion
from app.services.referential import log_activity

SEED_PATH = Path(__file__).parent / "data" / "referential_seed.json"
SYSTEM_EMAIL = "system@pr-review.local"


def _get_or_create_system_admin(db) -> User:
    """Compte technique servant d'auteur des règles importées."""
    user = db.scalar(select(User).where(User.email == SYSTEM_EMAIL))
    if user is None:
        user = User(
            email=SYSTEM_EMAIL,
            display_name="Import système",
            role=UserRole.admin,
            is_active=True,
            email_verified=True,
            password_hash=None,
        )
        db.add(user)
        db.flush()
    return user


def _get_actor(db, actor_email: str | None) -> User:
    if actor_email:
        user = db.scalar(select(User).where(User.email == actor_email.lower()))
        if user is None:
            raise SystemExit(f"Aucun utilisateur avec l'e-mail {actor_email!r}.")
        if user.role != UserRole.admin:
            raise SystemExit("L'acteur du seed doit être administrateur.")
        return user
    return _get_or_create_system_admin(db)


def _get_or_create_category(db, ct: ChecklistType, name: str, order: int) -> Category:
    cat = db.scalar(
        select(Category).where(
            Category.checklist_type == ct, Category.name == name
        )
    )
    if cat is None:
        cat = Category(checklist_type=ct, name=name, order_index=order)
        db.add(cat)
        db.flush()
    return cat


def _rule_exists(db, category_id, text: str) -> bool:
    """Vrai si une règle de cette catégorie a déjà ce libellé en version courante."""
    return db.scalar(
        select(RuleVersion.id)
        .join(Rule, Rule.id == RuleVersion.rule_id)
        .where(
            Rule.category_id == category_id,
            RuleVersion.is_current.is_(True),
            RuleVersion.text == text,
        )
        .limit(1)
    ) is not None


def run(actor_email: str | None = None) -> None:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    created_rules = 0
    skipped = 0
    try:
        actor = _get_actor(db, actor_email)

        for type_str, categories in data.items():
            ct = ChecklistType(type_str)
            for order, cat_data in enumerate(categories):
                category = _get_or_create_category(db, ct, cat_data["name"], order)

                for rule_data in cat_data["rules"]:
                    text = rule_data["text"]
                    if _rule_exists(db, category.id, text):
                        skipped += 1
                        continue

                    rule = Rule(
                        checklist_type=ct,
                        category_id=category.id,
                        status="active",
                        created_by=actor.id,
                    )
                    db.add(rule)
                    db.flush()

                    version = RuleVersion(
                        rule_id=rule.id,
                        version_number=1,
                        text=text,
                        subs=list(rule_data.get("subs", [])),
                        criticality=Criticality(rule_data.get("criticality", "recommended")),
                        is_current=True,
                        lifecycle=LifecycleState.approved,
                        proposed_by=actor.id,
                        reviewed_by=actor.id,
                    )
                    db.add(version)
                    db.flush()

                    log_activity(
                        db,
                        action="rule_created",
                        actor=actor,
                        checklist_type=ct,
                        rule_text=text,
                        rule_id=rule.id,
                        rule_version_id=version.id,
                        detail="Import initial du référentiel",
                    )
                    created_rules += 1

        db.commit()
        print(
            f"Seed terminé : {created_rules} règle(s) créée(s), "
            f"{skipped} ignorée(s) (déjà présentes)."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import initial du référentiel PR Review.")
    parser.add_argument(
        "--actor",
        dest="actor",
        default=None,
        help="E-mail d'un administrateur existant à qui attribuer l'import.",
    )
    args = parser.parse_args()
    run(actor_email=args.actor)
