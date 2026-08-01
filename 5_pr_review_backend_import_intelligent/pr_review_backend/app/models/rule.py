"""Modèles ORM du référentiel : règles et versions de règles (Lot 2).

Principe fondateur du projet — le VERSIONNEMENT IMMUABLE :

  * `Rule` est une identité stable (jamais réécrite après création).
  * `RuleVersion` porte le contenu (texte, sous-points, criticité). Toute
    « modification » d'une règle crée une NOUVELLE version ; on n'écrase jamais
    une version existante. Une seule version est `is_current` par règle.
  * Les `review_items` (Lot 3) pointeront vers un `rule_version_id` précis :
    c'est ce qui garantit la comparabilité historique quand le référentiel évolue.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ChecklistType, Criticality, LifecycleState


class Rule(Base):
    """Identité stable d'une règle. Son contenu vit dans `rule_versions`."""

    __tablename__ = "rules"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','retired')", name="ck_rules_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    checklist_type: Mapped[ChecklistType] = mapped_column(
        SAEnum(ChecklistType, name="checklist_type"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # 'active' = présente dans le référentiel ; 'retired' = retirée mais conservée.
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    category: Mapped["Category"] = relationship(back_populates="rules")  # noqa: F821
    versions: Mapped[list["RuleVersion"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="RuleVersion.version_number",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Rule {self.id} ({self.status})>"


class RuleVersion(Base):
    """Contenu IMMUABLE d'une règle à un instant donné."""

    __tablename__ = "rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_id", "version_number", name="uq_rule_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Sous-points de la règle (les "->" du prototype), liste de chaînes.
    subs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    criticality: Mapped[Criticality] = mapped_column(
        SAEnum(Criticality, name="criticality"),
        default=Criticality.recommended,
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lifecycle: Mapped[LifecycleState] = mapped_column(
        SAEnum(LifecycleState, name="lifecycle_state"),
        default=LifecycleState.pending,
        nullable=False,
    )
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rule: Mapped["Rule"] = relationship(back_populates="versions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RuleVersion rule={self.rule_id} v{self.version_number} {self.lifecycle.value}>"
