"""
Routes de la validation tierce (Lot 4).

Deux groupes :
  - sous `/reviews/{id}/share` : l'auteur génère un lien de partage ;
  - sous `/share/...` : révocation, métadonnées par token, et validation.

Sécurité clé (conforme à la spec) : la VALIDATION exige un compte authentifié
avec le rôle `reviewer` ou `admin`, ET que ce compte soit une cible explicite du
lien (ou l'admin). L'écran « Qui êtes-vous ? » du front n'oriente que l'affichage :
l'autorisation réelle est vérifiée ici, côté serveur, à partir du JWT.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.deps import get_current_user, require_reviewer
from app.models.user import User
from app.models.enums import UserRole, ReviewStatus
from app.models.review import Review
from app.models.share import ShareLink, ShareTarget
from app.schemas.share import (
    ShareCreate,
    ShareLinkOut,
    ShareTargetOut,
    SharedReviewMeta,
    ValidationCreate,
    ValidationOut,
)
from app.services import validation as svc


# ==========================================================================
# Routeur 1 : création de partage sous /reviews/{id}/share
# ==========================================================================
review_share_router = APIRouter(prefix="/reviews", tags=["validation tierce"])


def _get_review_or_404(db: Session, review_id: uuid.UUID) -> Review:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revue introuvable.")
    return review


def _share_out(db: Session, link: ShareLink) -> ShareLinkOut:
    targets = []
    for t in link.targets:
        u = db.get(User, t.reviewer_id)
        targets.append(
            ShareTargetOut(reviewer_id=t.reviewer_id,
                           reviewer_name=u.display_name if u else None)
        )
    return ShareLinkOut(
        id=link.id,
        review_id=link.review_id,
        token=link.token,
        created_by=link.created_by,
        expires_at=link.expires_at,
        revoked=link.revoked,
        created_at=link.created_at,
        targets=targets,
    )


@review_share_router.post(
    "/{review_id}/share",
    response_model=ShareLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_share(
    review_id: uuid.UUID,
    payload: ShareCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Génère un lien de partage ciblant des reviewers explicites (auteur only)."""
    review = _get_review_or_404(db, review_id)
    if review.author_id != user.id and user.role != UserRole.admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Seul l'auteur peut partager cette revue."
        )

    # Vérifie que les cibles existent et ont un rôle habilité à valider.
    for rid in payload.reviewer_ids:
        target = db.get(User, rid)
        if target is None or not target.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Reviewer introuvable ou inactif : {rid}."
            )
        if target.role == UserRole.user:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"L'utilisateur {target.display_name} n'a pas le rôle reviewer/admin.",
            )

    link = svc.create_share_link(
        db, review=review, creator=user,
        reviewer_ids=payload.reviewer_ids, ttl_days=payload.ttl_days,
    )
    db.commit()
    db.refresh(link)
    return _share_out(db, link)


@review_share_router.get("/{review_id}/shares", response_model=list[ShareLinkOut])
def list_shares(
    review_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste les liens de partage d'une revue (auteur ou admin)."""
    review = _get_review_or_404(db, review_id)
    if review.author_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès non autorisé.")
    links = db.scalars(
        select(ShareLink).where(ShareLink.review_id == review.id)
        .order_by(ShareLink.created_at.desc())
    ).all()
    return [_share_out(db, l) for l in links]


# ==========================================================================
# Routeur 2 : opérations sur les liens sous /share/...
# ==========================================================================
share_router = APIRouter(prefix="/share", tags=["validation tierce"])


@share_router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Révoque un lien de partage (auteur de la revue ou admin)."""
    link = db.get(ShareLink, share_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien introuvable.")
    review = db.get(Review, link.review_id)
    if review is None or (review.author_id != user.id and user.role != UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Révocation non autorisée.")
    svc.revoke_share_link(db, link=link)
    db.commit()


@share_router.get("/{token}", response_model=SharedReviewMeta)
def shared_review_meta(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Métadonnées d'une revue partagée (lecture limitée).

    Exige un compte authentifié : même la consultation via lien passe par le JWT.
    `can_validate` indique si l'appelant est habilité à statuer sur cette revue.
    """
    link = svc.get_active_link_by_token(db, token)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien invalide, révoqué ou expiré.")

    review = db.get(Review, link.review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revue introuvable.")

    author = db.get(User, review.author_id)
    from app.models.review import ReviewItem
    from sqlalchemy import func
    item_count = db.scalar(
        select(func.count()).select_from(ReviewItem)
        .where(ReviewItem.review_id == review.id)
    ) or 0

    can_validate = (
        user.role in (UserRole.reviewer, UserRole.admin)
        and (user.role == UserRole.admin or svc.is_link_target(db, link=link, user=user))
    )

    return SharedReviewMeta(
        review_id=review.id,
        report_name=review.report_name,
        checklist_type=review.checklist_type,
        status=review.status,
        compliance_score=review.compliance_score,
        author_name=author.display_name if author else None,
        item_count=int(item_count),
        expires_at=link.expires_at,
        can_validate=can_validate,
    )


@share_router.post("/{token}/validate", response_model=ValidationOut)
def validate_shared_review(
    token: str,
    payload: ValidationCreate,
    reviewer: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """
    Approuver ou refuser une revue partagée (reviewer/admin authentifié + ciblé).

    - `approved` → revue `validated` ; `rejected` → `changes_requested`.
    - Commentaires par point optionnels.
    """
    link = svc.get_active_link_by_token(db, token)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien invalide, révoqué ou expiré.")

    # Autorisation : admin, ou reviewer explicitement ciblé par CE lien.
    if reviewer.role != UserRole.admin and not svc.is_link_target(db, link=link, user=reviewer):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Vous n'êtes pas destinataire de ce partage.",
        )

    review = db.get(Review, link.review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revue introuvable.")
    if review.status == ReviewStatus.validated:
        raise HTTPException(status.HTTP_409_CONFLICT, "Revue déjà validée.")

    item_comments = {ic.review_item_id: ic.comment for ic in payload.item_comments}
    validation = svc.submit_validation(
        db, review=review, reviewer=reviewer, decision=payload.decision,
        global_comment=payload.global_comment, item_comments=item_comments,
    )
    from app.services import audit
    audit.record(
        db, action="review.validate", entity="reviews", entity_id=review.id,
        user_id=reviewer.id,
        metadata={"decision": payload.decision, "resulting_status": review.status.value},
    )
    db.commit()
    db.refresh(validation)
    db.refresh(review)

    out = ValidationOut(
        id=validation.id,
        review_id=validation.review_id,
        reviewer_id=validation.reviewer_id,
        reviewer_name=reviewer.display_name,
        decision=validation.decision,
        global_comment=validation.global_comment,
        created_at=validation.created_at,
        resulting_status=review.status,
    )
    return out
