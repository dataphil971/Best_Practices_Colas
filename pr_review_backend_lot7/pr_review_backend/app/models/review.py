"""
Modèles ORM des revues (Lot 3).

Une `Review` fige, à sa création, un ensemble de `ReviewItem`. Chaque item pointe
vers un `rule_version_id` précis — le SNAPSHOT de la règle telle qu'elle existait
au moment de la revue. Même si le référentiel évolue ensuite (nouvelle version,
retrait), les items d'une revue passée ne bougent pas : c'est l'invariant qui
garantit la comparabilité historique.

Le `compliance_score` est mis en cache sur la revue et recalculé au fil de l'eau
à chaque mise à jour d'item (voir services/review.py).
"""
import uuid
from datetime import datetime, date

from sqlalchemy import (
    String,
    Integer,
    Text,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ChecklistType, ReviewStatus, ItemStatus, ProgressState


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_name: Mapped[str] = mapped_column(Text, nullable=False)
    checklist_type: Mapped[ChecklistType] = mapped_column(
        SAEnum(ChecklistType, name="checklist_type"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status"),
        default=ReviewStatus.in_progress,
        nullable=False,
        index=True,
    )
    # Score de conformité mis en cache (0–100), recalculé à chaque màj d'item.
    compliance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["ReviewItem"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Review {self.report_name!r} ({self.status.value})>"


class ReviewItem(Base):
    """Point de contrôle d'une revue : snapshot d'une règle + son évaluation."""

    __tablename__ = "review_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Snapshot : la version exacte de la règle évaluée (jamais la règle mutable).
    rule_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_versions.id"), nullable=False
    )
    status: Mapped[ItemStatus] = mapped_column(
        SAEnum(ItemStatus, name="item_status"),
        default=ItemStatus.unset,
        nullable=False,
    )
    progress: Mapped[ProgressState] = mapped_column(
        SAEnum(ProgressState, name="progress_state"),
        default=ProgressState.todo,
        nullable=False,
    )
    # Bloc remédiation (aligné sur le prototype).
    comment: Mapped[str] = mapped_column(Text, default="", nullable=True)
    risk: Mapped[str] = mapped_column(Text, default="", nullable=True)
    risk_comment: Mapped[str] = mapped_column(Text, default="", nullable=True)
    proposed_solution: Mapped[str] = mapped_column(Text, default="", nullable=True)
    estimated_days: Mapped[str] = mapped_column(Text, default="", nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    definition_of_done: Mapped[str] = mapped_column(Text, default="", nullable=True)
    priority: Mapped[str] = mapped_column(Text, default="", nullable=True)
    responsible: Mapped[str] = mapped_column(Text, default="", nullable=True)
    last_update: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    review: Mapped["Review"] = relationship(back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ReviewItem {self.id} {self.status.value}>"
