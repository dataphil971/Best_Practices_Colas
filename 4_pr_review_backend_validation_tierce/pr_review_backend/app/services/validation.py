"""
Service de la validation tierce (Lot 4).

Regroupe les invariants de partage et de validation :

  - GÉNÉRATION de token : 256 bits d'entropie, base64url (secrets.token_urlsafe).
  - EXPIRATION obligatoire ; un lien révoqué ou expiré n'ouvre plus rien.
  - CIBLAGE explicite : un partage vise des reviewers nommés (`share_targets`).
    La visibilité d'une revue pour un reviewer découle UNIQUEMENT d'un partage le
    ciblant (ou du fait qu'il soit l'auteur / un admin). Aucun accès de large
    périmètre.
  - VALIDATION : approbation → `validated` ; refus → `changes_requested`. Les
    commentaires par point sont attachés à la validation.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, exists, and_
from sqlalchemy.orm import Session

from app.models.enums import UserRole, ReviewStatus
from app.models.user import User
from app.models.review import Review, ReviewItem
from app.models.share import (
    ShareLink,
    ShareTarget,
    Validation,
    ValidationItemComment,
)

# Durée de validité par défaut d'un lien de partage (jours).
DEFAULT_SHARE_TTL_DAYS = 14


# --------------------------------------------------------------------------
# Création / révocation de partage
# --------------------------------------------------------------------------
def create_share_link(
    db: Session,
    *,
    review: Review,
    creator: User,
    reviewer_ids: list[uuid.UUID],
    ttl_days: int = DEFAULT_SHARE_TTL_DAYS,
) -> ShareLink:
    """
    Génère un lien de partage ciblant des reviewers explicites.

    Le token porte 256 bits d'entropie. L'expiration est obligatoire.
    """
    token = secrets.token_urlsafe(32)  # 32 octets = 256 bits
    link = ShareLink(
        review_id=review.id,
        token=token,
        created_by=creator.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
        revoked=False,
    )
    db.add(link)
    db.flush()

    # Déduplique les cibles.
    for rid in dict.fromkeys(reviewer_ids):
        db.add(ShareTarget(share_link_id=link.id, reviewer_id=rid))
    db.flush()
    return link


def revoke_share_link(db: Session, *, link: ShareLink) -> ShareLink:
    link.revoked = True
    db.flush()
    return link


# --------------------------------------------------------------------------
# Résolution / validité d'un token
# --------------------------------------------------------------------------
def get_active_link_by_token(db: Session, token: str) -> ShareLink | None:
    """Retourne le lien s'il existe, n'est pas révoqué et n'est pas expiré."""
    link = db.scalar(select(ShareLink).where(ShareLink.token == token))
    if link is None or link.revoked:
        return None
    expires = link.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    return link


def is_link_target(db: Session, *, link: ShareLink, user: User) -> bool:
    """Vrai si l'utilisateur fait partie des reviewers ciblés par ce lien."""
    return db.scalar(
        select(
            exists().where(
                and_(
                    ShareTarget.share_link_id == link.id,
                    ShareTarget.reviewer_id == user.id,
                )
            )
        )
    ) or False


# --------------------------------------------------------------------------
# Politique de visibilité d'une revue
# --------------------------------------------------------------------------
def can_user_view_review(db: Session, *, review: Review, user: User) -> bool:
    """
    Détermine si un utilisateur peut consulter une revue :

      - l'admin voit tout ;
      - l'auteur voit la sienne ;
      - un reviewer voit une revue s'il est ciblé par un lien de partage ACTIF
        pour cette revue.
    """
    if user.role == UserRole.admin or review.author_id == user.id:
        return True

    now = datetime.now(timezone.utc)
    # Existe-t-il un lien actif ciblant cet utilisateur pour cette revue ?
    return db.scalar(
        select(
            exists()
            .where(ShareLink.review_id == review.id)
            .where(ShareLink.revoked.is_(False))
            .where(ShareLink.expires_at >= now)
            .where(
                ShareTarget.share_link_id == ShareLink.id,
            )
            .where(ShareTarget.reviewer_id == user.id)
        )
    ) or False


def list_visible_review_ids_for_reviewer(db: Session, user: User) -> list[uuid.UUID]:
    """IDs des revues partagées à ce reviewer via un lien actif."""
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(ShareLink.review_id)
        .join(ShareTarget, ShareTarget.share_link_id == ShareLink.id)
        .where(
            ShareTarget.reviewer_id == user.id,
            ShareLink.revoked.is_(False),
            ShareLink.expires_at >= now,
        )
        .distinct()
    ).all()
    return [r[0] for r in rows]


# --------------------------------------------------------------------------
# Validation (approbation / refus)
# --------------------------------------------------------------------------
def submit_validation(
    db: Session,
    *,
    review: Review,
    reviewer: User,
    decision: str,               # 'approved' | 'rejected'
    global_comment: str | None,
    item_comments: dict[uuid.UUID, str],
) -> Validation:
    """
    Enregistre une validation et fait évoluer le statut de la revue.

      - 'approved'  → review.status = validated (+ validated_at) ;
      - 'rejected'  → review.status = changes_requested.

    Les commentaires par point ne sont retenus que pour des items appartenant
    réellement à la revue (garde-fou d'intégrité).
    """
    if decision not in ("approved", "rejected"):
        raise ValueError("decision doit valoir 'approved' ou 'rejected'.")

    validation = Validation(
        review_id=review.id,
        reviewer_id=reviewer.id,
        decision=decision,
        global_comment=global_comment,
    )
    db.add(validation)
    db.flush()

    if item_comments:
        valid_item_ids = {
            r[0]
            for r in db.execute(
                select(ReviewItem.id).where(ReviewItem.review_id == review.id)
            ).all()
        }
        for item_id, comment in item_comments.items():
            if item_id in valid_item_ids and comment:
                db.add(
                    ValidationItemComment(
                        validation_id=validation.id,
                        review_item_id=item_id,
                        comment=comment,
                    )
                )

    if decision == "approved":
        review.status = ReviewStatus.validated
        review.validated_at = datetime.now(timezone.utc)
    else:
        review.status = ReviewStatus.changes_requested

    db.flush()
    return validation
