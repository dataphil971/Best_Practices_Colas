"""Modèle ORM des catégories du référentiel (Lot 2).

Une catégorie appartient à un référentiel (`checklist_type`) et regroupe des
règles. L'unicité (checklist_type, name) évite les doublons par référentiel.
"""
import uuid

from sqlalchemy import String, Integer, Enum as SAEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ChecklistType


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("checklist_type", "name", name="uq_category_type_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    checklist_type: Mapped[ChecklistType] = mapped_column(
        SAEnum(ChecklistType, name="checklist_type"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rules: Mapped[list["Rule"]] = relationship(  # noqa: F821
        back_populates="category", cascade="save-update"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category {self.checklist_type.value}/{self.name}>"
