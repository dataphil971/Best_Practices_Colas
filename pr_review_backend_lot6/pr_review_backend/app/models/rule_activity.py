"""Journal d'activité du référentiel (Lot 2).

Distinct de `audit_log` (technique, global, à venir) : cette table est présentée
dans l'espace admin du référentiel. Elle répond à « qui a fait quoi » avec
attribution multi-admins, filtrable par action et par acteur.

Le libellé de la règle (`rule_text`) est figé au moment de l'action : ainsi le
journal reste lisible même si la règle est ensuite retirée ou reformulée.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ChecklistType

# Actions traçables sur le référentiel (alignées sur le CHECK SQL de la spec).
ACTIVITY_ACTIONS = (
    "rule_created",
    "rule_proposed",
    "rule_revised",
    "rule_approved",
    "rule_rejected",
    "rule_retired",
    "rule_restored",
)


class RuleActivity(Base):
    __tablename__ = "rule_activity"
    __table_args__ = (
        CheckConstraint(
            "action IN ('rule_created','rule_proposed','rule_revised',"
            "'rule_approved','rule_rejected','rule_retired','rule_restored')",
            name="ck_activity_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id", ondelete="SET NULL"), nullable=True
    )
    rule_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rule_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    checklist_type: Mapped[ChecklistType] = mapped_column(
        SAEnum(ChecklistType, name="checklist_type"), nullable=False
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # ex. 'v2 → v3', motif
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RuleActivity {self.action} by {self.actor_id}>"
