"""
Service du référentiel versionné (Lot 2).

Ce module concentre TOUS les invariants métier du référentiel. Les routes ne
font qu'appeler ces fonctions : la logique de versionnement n'est écrite qu'une
fois, testée une fois.

Invariants garantis :
  1. Immuabilité : on ne modifie jamais une `RuleVersion` existante. Reformuler
     = créer `version_number + 1` avec `is_current = true` et basculer l'ancienne
     à `is_current = false`, dans la MÊME transaction.
  2. Version courante unique : au plus une version `is_current` par règle
     (garanti aussi par l'index partiel `uniq_current_version`).
  3. Traçabilité : toute action sensible écrit une ligne dans `rule_activity`
     avec le libellé figé de la règle et l'acteur.

La transaction (commit/rollback) est gérée par l'appelant (la route), pour qu'un
enchaînement d'opérations reste atomique.
"""
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.enums import ChecklistType, Criticality, LifecycleState, UserRole
from app.models.category import Category
from app.models.rule import Rule, RuleVersion
from app.models.rule_activity import RuleActivity
from app.models.user import User


# --------------------------------------------------------------------------
# Journal d'activité
# --------------------------------------------------------------------------
def log_activity(
    db: Session,
    *,
    action: str,
    actor: User,
    checklist_type: ChecklistType,
    rule_text: str,
    rule_id: uuid.UUID | None = None,
    rule_version_id: uuid.UUID | None = None,
    detail: str | None = None,
) -> RuleActivity:
    """Enregistre une entrée dans le journal d'activité du référentiel."""
    entry = RuleActivity(
        action=action,
        actor_id=actor.id,
        checklist_type=checklist_type,
        rule_text=rule_text,
        rule_id=rule_id,
        rule_version_id=rule_version_id,
        detail=detail,
    )
    db.add(entry)
    return entry


# --------------------------------------------------------------------------
# Lecture
# --------------------------------------------------------------------------
def get_current_version(db: Session, rule_id: uuid.UUID) -> RuleVersion | None:
    """Retourne la version courante d'une règle (ou None)."""
    return db.scalar(
        select(RuleVersion).where(
            RuleVersion.rule_id == rule_id, RuleVersion.is_current.is_(True)
        )
    )


def _next_version_number(db: Session, rule_id: uuid.UUID) -> int:
    current_max = db.scalar(
        select(func.max(RuleVersion.version_number)).where(
            RuleVersion.rule_id == rule_id
        )
    )
    return (current_max or 0) + 1


# --------------------------------------------------------------------------
# Création / proposition
# --------------------------------------------------------------------------
def create_rule(
    db: Session,
    *,
    actor: User,
    checklist_type: ChecklistType,
    category: Category,
    text: str,
    subs: list[str],
    criticality: Criticality,
) -> Rule:
    """
    Crée une règle avec sa version 1.

    Un admin voit sa règle entrer directement au référentiel (`approved`) ;
    tout autre rôle produit une proposition (`pending`) qui devra être validée.
    """
    is_admin = actor.role == UserRole.admin
    lifecycle = LifecycleState.approved if is_admin else LifecycleState.pending

    rule = Rule(
        checklist_type=checklist_type,
        category_id=category.id,
        status="active",
        created_by=actor.id,
    )
    db.add(rule)
    db.flush()  # pour obtenir rule.id

    version = RuleVersion(
        rule_id=rule.id,
        version_number=1,
        text=text,
        subs=subs,
        criticality=criticality,
        is_current=True,
        lifecycle=lifecycle,
        proposed_by=actor.id,
        reviewed_by=actor.id if is_admin else None,
    )
    db.add(version)
    db.flush()

    # 'rule_created' si admin (entre directement) sinon 'rule_proposed'.
    log_activity(
        db,
        action="rule_created" if is_admin else "rule_proposed",
        actor=actor,
        checklist_type=checklist_type,
        rule_text=text,
        rule_id=rule.id,
        rule_version_id=version.id,
    )
    return rule


# --------------------------------------------------------------------------
# Reformulation → nouvelle version immuable
# --------------------------------------------------------------------------
def revise_rule(
    db: Session,
    *,
    actor: User,
    rule: Rule,
    text: str,
    subs: list[str],
    criticality: Criticality,
    category: Category | None = None,
) -> RuleVersion:
    """
    Reformule une règle : crée une nouvelle version courante approuvée et
    bascule l'ancienne à `is_current = false`. N'écrase JAMAIS l'existant.
    Réservé à l'admin (contrôlé au niveau de la route).
    """
    old = get_current_version(db, rule.id)
    old_number = old.version_number if old else 0
    if old is not None:
        old.is_current = False

    if category is not None:
        rule.category_id = category.id

    new_version = RuleVersion(
        rule_id=rule.id,
        version_number=_next_version_number(db, rule.id),
        text=text,
        subs=subs,
        criticality=criticality,
        is_current=True,
        lifecycle=LifecycleState.approved,  # révision admin = directement active
        proposed_by=actor.id,
        reviewed_by=actor.id,
    )
    db.add(new_version)
    db.flush()

    log_activity(
        db,
        action="rule_revised",
        actor=actor,
        checklist_type=rule.checklist_type,
        rule_text=text,
        rule_id=rule.id,
        rule_version_id=new_version.id,
        detail=f"v{old_number} → v{new_version.version_number}",
    )
    return new_version


# --------------------------------------------------------------------------
# Approbation / rejet d'une proposition
# --------------------------------------------------------------------------
def approve_version(db: Session, *, actor: User, version: RuleVersion) -> RuleVersion:
    """Approuve une version en attente : elle entre au référentiel actif."""
    version.lifecycle = LifecycleState.approved
    version.reviewed_by = actor.id
    db.flush()

    log_activity(
        db,
        action="rule_approved",
        actor=actor,
        checklist_type=version.rule.checklist_type,
        rule_text=version.text,
        rule_id=version.rule_id,
        rule_version_id=version.id,
    )
    return version


def reject_version(
    db: Session, *, actor: User, version: RuleVersion, reason: str
) -> RuleVersion:
    """
    Rejette une proposition (avec motif). La version cesse d'être courante :
    une proposition rejetée ne doit pas rester la version active de la règle.
    """
    version.lifecycle = LifecycleState.rejected
    version.reviewed_by = actor.id
    version.review_comment = reason
    version.is_current = False
    db.flush()

    log_activity(
        db,
        action="rule_rejected",
        actor=actor,
        checklist_type=version.rule.checklist_type,
        rule_text=version.text,
        rule_id=version.rule_id,
        rule_version_id=version.id,
        detail=reason,
    )
    return version


# --------------------------------------------------------------------------
# Retrait / restauration (réversible, historique conservé)
# --------------------------------------------------------------------------
def retire_rule(db: Session, *, actor: User, rule: Rule) -> Rule:
    """Retire une règle du référentiel actif (réversible)."""
    rule.status = "retired"
    db.flush()
    current = get_current_version(db, rule.id)
    log_activity(
        db,
        action="rule_retired",
        actor=actor,
        checklist_type=rule.checklist_type,
        rule_text=current.text if current else "(règle sans version)",
        rule_id=rule.id,
        rule_version_id=current.id if current else None,
    )
    return rule


def restore_rule(db: Session, *, actor: User, rule: Rule) -> Rule:
    """Restaure une règle retirée."""
    rule.status = "active"
    db.flush()
    current = get_current_version(db, rule.id)
    log_activity(
        db,
        action="rule_restored",
        actor=actor,
        checklist_type=rule.checklist_type,
        rule_text=current.text if current else "(règle sans version)",
        rule_id=rule.id,
        rule_version_id=current.id if current else None,
    )
    return rule
