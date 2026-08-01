"""
Modèles ORM de la validation tierce (Lot 4).

Deux mécaniques complémentaires :

  1. PARTAGE CIBLÉ — un `ShareLink` (token aléatoire 256 bits, expiration
     obligatoire, révocable) ouvre l'accès à une revue. Il vise un ou plusieurs
     reviewers explicites via `ShareTarget`. C'est la SEULE façon d'élargir la
     visibilité d'une revue à un reviewer : il n'existe aucun accès de large
     périmètre (pas de « toutes les revues de l'équipe »). Seul l'admin voit tout.

  2. VALIDATION — un reviewer/admin authentifié approuve ou refuse la revue via
     une `Validation`, éventuellement assortie de commentaires par point
     (`ValidationItemComment`). Un refus fait passer la revue en
     `changes_requested` ; l'auteur corrige puis resoumet.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShareLink(Base):
    __tablename__ = "share_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    targets: Mapped[list["ShareTarget"]] = relationship(
        back_populates="share_link", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ShareLink review={self.review_id} revoked={self.revoked}>"


class ShareTarget(Base):
    """Reviewer explicitement ciblé par un partage (clé composite)."""

    __tablename__ = "share_targets"

    share_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("share_links.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    share_link: Mapped["ShareLink"] = relationship(back_populates="targets")


class Validation(Base):
    __tablename__ = "validations"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved','rejected')", name="ck_validation_decision"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String, nullable=False)  # approved | rejected
    global_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    item_comments: Mapped[list["ValidationItemComment"]] = relationship(
        back_populates="validation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Validation {self.decision} review={self.review_id}>"


class ValidationItemComment(Base):
    __tablename__ = "validation_item_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validations.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    validation: Mapped["Validation"] = relationship(back_populates="item_comments")
