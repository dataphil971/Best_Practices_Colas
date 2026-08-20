"""
Routes admin des paramètres applicatifs et de l'audit (Lot 7, §5.7).
"""
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.deps import require_admin
from app.models.user import User
from app.models.audit import AuditLog
from app.services import settings as settings_svc
from app.services import audit
from app.services import retention as retention_svc

router = APIRouter(prefix="/admin", tags=["admin — paramètres & audit"])


# --- Schémas ---------------------------------------------------------------
class RetentionIn(BaseModel):
    days: int = Field(ge=1, le=3650)


class RoleMappingIn(BaseModel):
    mapping: dict[str, str] = Field(default_factory=dict)


class AuditEntryOut(BaseModel):
    id: int
    user_id: uuid.UUID | None = None
    action: str
    entity: str
    entity_id: uuid.UUID | None = None
    ip: str | None = None
    created_at: str


# --- Paramètres ------------------------------------------------------------
@router.get("/settings")
def get_settings(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lit les paramètres applicatifs (dont retention_days et role_mapping)."""
    return {
        "retention_days": settings_svc.get_retention_days(db),
        "role_mapping": settings_svc.get_role_mapping(db),
    }


@router.put("/settings/retention")
def update_retention(
    payload: RetentionIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Modifie la durée de rétention des fichiers importés (jours)."""
    days = settings_svc.set_retention_days(db, days=payload.days, updated_by=admin.id)
    audit.record(
        db, action="settings.retention", entity="app_settings",
        user_id=admin.id, metadata={"days": days},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {"retention_days": days}


@router.put("/settings/role-mapping")
def update_role_mapping(
    payload: RoleMappingIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mappe des groupes Entra ID vers des rôles applicatifs (audité)."""
    mapping = settings_svc.set_role_mapping(db, mapping=payload.mapping, updated_by=admin.id)
    audit.record(
        db, action="settings.role_mapping", entity="app_settings",
        user_id=admin.id, metadata={"mapping": mapping},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {"role_mapping": mapping}


# --- Purge de rétention (déclenchement manuel ; planifiable via Celery beat) --
@router.post("/settings/retention/purge")
def trigger_purge(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Déclenche manuellement la purge de rétention."""
    result = retention_svc.run_retention_purge(db)
    db.commit()
    return result


# --- Audit -----------------------------------------------------------------
@router.get("/audit", response_model=list[AuditEntryOut])
def list_audit(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    action: str | None = None,
    entity: str | None = None,
    limit: int = 100,
):
    """Consulte le journal d'audit (filtrable par action et entité)."""
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if entity:
        query = query.where(AuditLog.entity == entity)
    query = query.order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    entries = db.scalars(query).all()
    return [
        AuditEntryOut(
            id=e.id, user_id=e.user_id, action=e.action, entity=e.entity,
            entity_id=e.entity_id, ip=str(e.ip) if e.ip else None,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]
