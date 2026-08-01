"""
Routes de gestion des règles du référentiel (Lot 2).

Couvre l'ensemble du cycle de vie d'une règle :
  - proposition (tout utilisateur → pending ; admin → approuvée) ;
  - reformulation (admin → nouvelle version immuable) ;
  - file d'attente des propositions et approbation / rejet (admin) ;
  - retrait / restauration réversibles (admin) ;
  - historique navigable des versions.

La transaction est validée (`db.commit()`) au niveau de la route pour garantir
l'atomicité de chaque opération de versionnement.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.deps import get_current_user, require_admin
from app.models.user import User
from app.models.category import Category
from app.models.rule import Rule, RuleVersion
from app.models.enums import LifecycleState
from app.schemas.referential import (
    RuleCreate,
    RuleRevise,
    RuleOut,
    RuleVersionOut,
    RejectPayload,
)
from app.services import referential as svc
from app.services.serializers import rule_to_out

router = APIRouter(prefix="/rules", tags=["référentiel — règles"])


# --------------------------------------------------------------------------
# Helpers internes
# --------------------------------------------------------------------------
def _get_rule_or_404(db: Session, rule_id: uuid.UUID) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Règle introuvable.")
    return rule


def _get_category_checked(
    db: Session, category_id: uuid.UUID, checklist_type
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catégorie introuvable.")
    if category.checklist_type != checklist_type:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La catégorie n'appartient pas au même référentiel que la règle.",
        )
    return category


# --------------------------------------------------------------------------
# Proposer une règle
# --------------------------------------------------------------------------
@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def propose_rule(
    payload: RuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Proposer une règle. Admin → approuvée d'office ; sinon en attente."""
    category = _get_category_checked(db, payload.category_id, payload.checklist_type)
    rule = svc.create_rule(
        db,
        actor=user,
        checklist_type=payload.checklist_type,
        category=category,
        text=payload.text,
        subs=payload.subs,
        criticality=payload.criticality,
    )
    db.commit()
    return rule_to_out(db, rule, category_name=category.name)


# --------------------------------------------------------------------------
# File d'attente des propositions (admin)
# --------------------------------------------------------------------------
@router.get("/pending", response_model=list[RuleVersionOut])
def list_pending(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    q: str | None = None,
):
    """Propositions en attente d'approbation, avec recherche texte optionnelle."""
    query = select(RuleVersion).where(
        RuleVersion.lifecycle == LifecycleState.pending,
        RuleVersion.is_current.is_(True),
    )
    if q:
        query = query.where(RuleVersion.text.ilike(f"%{q}%"))
    query = query.order_by(RuleVersion.created_at.asc())
    return list(db.scalars(query).all())


# --------------------------------------------------------------------------
# Règles retirées (admin)
# --------------------------------------------------------------------------
@router.get("/retired", response_model=list[RuleOut])
def list_retired(
    type: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Liste les règles retirées d'un référentiel (historique consultable)."""
    rules = db.scalars(
        select(Rule)
        .where(Rule.checklist_type == type, Rule.status == "retired")
        .order_by(Rule.created_at.desc())
    ).all()
    return [rule_to_out(db, r) for r in rules]


# --------------------------------------------------------------------------
# Reformuler une règle → nouvelle version (admin)
# --------------------------------------------------------------------------
@router.patch("/{rule_id}", response_model=RuleOut)
def revise_rule(
    rule_id: uuid.UUID,
    payload: RuleRevise,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reformuler une règle : crée une nouvelle version (jamais d'écrasement)."""
    rule = _get_rule_or_404(db, rule_id)
    category = None
    if payload.category_id is not None:
        category = _get_category_checked(db, payload.category_id, rule.checklist_type)

    svc.revise_rule(
        db,
        actor=admin,
        rule=rule,
        text=payload.text,
        subs=payload.subs,
        criticality=payload.criticality,
        category=category,
    )
    db.commit()
    return rule_to_out(db, rule)


# --------------------------------------------------------------------------
# Approuver / rejeter une version (admin)
# --------------------------------------------------------------------------
@router.post("/{version_id}/approve", response_model=RuleVersionOut)
def approve(
    version_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Approuver une proposition en attente → elle entre au référentiel."""
    version = db.get(RuleVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable.")
    if version.lifecycle != LifecycleState.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Seule une proposition en attente peut être approuvée."
        )
    svc.approve_version(db, actor=admin, version=version)
    from app.services import audit
    audit.record(
        db, action="rule.approve", entity="rule_versions", entity_id=version.id,
        user_id=admin.id, metadata={"rule_id": str(version.rule_id)},
    )
    db.commit()
    db.refresh(version)
    return version


@router.post("/{version_id}/reject", response_model=RuleVersionOut)
def reject(
    version_id: uuid.UUID,
    payload: RejectPayload,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Rejeter une proposition (avec motif obligatoire)."""
    version = db.get(RuleVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable.")
    if version.lifecycle != LifecycleState.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Seule une proposition en attente peut être rejetée."
        )
    svc.reject_version(db, actor=admin, version=version, reason=payload.reason)
    db.commit()
    db.refresh(version)
    return version


# --------------------------------------------------------------------------
# Retrait / restauration (admin)
# --------------------------------------------------------------------------
@router.post("/{rule_id}/retire", response_model=RuleOut)
def retire(
    rule_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retirer une règle du référentiel actif (réversible)."""
    rule = _get_rule_or_404(db, rule_id)
    if rule.status == "retired":
        raise HTTPException(status.HTTP_409_CONFLICT, "Règle déjà retirée.")
    svc.retire_rule(db, actor=admin, rule=rule)
    db.commit()
    return rule_to_out(db, rule)


@router.post("/{rule_id}/restore", response_model=RuleOut)
def restore(
    rule_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Restaurer une règle retirée."""
    rule = _get_rule_or_404(db, rule_id)
    if rule.status == "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Règle déjà active.")
    svc.restore_rule(db, actor=admin, rule=rule)
    db.commit()
    return rule_to_out(db, rule)


# --------------------------------------------------------------------------
# Historique des versions d'une règle
# --------------------------------------------------------------------------
@router.get("/{rule_id}/versions", response_model=list[RuleVersionOut])
def list_versions(
    rule_id: uuid.UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sort: str = "recent",
):
    """Historique des versions d'une règle (navigable et triable)."""
    _get_rule_or_404(db, rule_id)
    order = (
        RuleVersion.version_number.desc()
        if sort == "recent"
        else RuleVersion.version_number.asc()
    )
    versions = db.scalars(
        select(RuleVersion).where(RuleVersion.rule_id == rule_id).order_by(order)
    ).all()
    return list(versions)
