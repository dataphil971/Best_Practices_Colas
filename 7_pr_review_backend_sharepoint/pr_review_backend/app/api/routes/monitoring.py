"""Routes de monitoring (Lot 7, §5.6)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.deps import get_current_user
from app.models.user import User
from app.models.enums import UserRole
from app.models.review import Review
from app.services import monitoring as svc
from app.services.validation import can_user_view_review

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/portfolio")
def get_portfolio(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    type: str | None = None,
    status_filter: str | None = None,
):
    """Agrégats portefeuille (scores, bloquants, avancement), filtrables."""
    return svc.portfolio(db, user=user, checklist_type=type, status_filter=status_filter)


@router.get("/reviews/{review_id}")
def get_review_progress(
    review_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Détail d'avancement d'une revue (par catégorie, par remédiation)."""
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revue introuvable.")
    if user.role != UserRole.admin and review.author_id != user.id:
        if not can_user_view_review(db, review=review, user=user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès non autorisé.")
    return svc.review_progress(db, review=review)
