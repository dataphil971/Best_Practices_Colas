"""Routes de gestion des utilisateurs (réservées à l'admin)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.deps import require_admin
from app.models.user import User
from app.schemas.user import UserOut, RoleUpdate, ActiveUpdate

router = APIRouter(prefix="/users", tags=["utilisateurs (admin)"])


@router.get("", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    q: str | None = None,
):
    query = db.query(User)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (User.email.ilike(like)) | (User.display_name.ilike(like))
        )
    return query.order_by(User.created_at.desc()).all()


@router.patch("/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: uuid.UUID,
    payload: RoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    target.role = payload.role
    db.commit()
    db.refresh(target)
    return target


@router.patch("/{user_id}/active", response_model=UserOut)
def update_active(
    user_id: uuid.UUID,
    payload: ActiveUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    if target.id == admin.id and not payload.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un admin ne peut pas se désactiver lui-même.")
    target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return target
