"""
Modèles ORM de l'audit et des paramètres applicatifs (Lot 7).

  - `AuditLog` : journal d'audit TECHNIQUE et GLOBAL, immuable. Distinct de
    `rule_activity` (journal métier du référentiel présenté aux admins). Toute
    action sensible y est tracée avec IP et horodatage. On n'expose ni update ni
    delete : l'immuabilité est une garantie de conformité.

  - `AppSetting` : paramètres modifiables par l'admin (clé/valeur JSON), dont
    `retention_days` (durée de rétention des fichiers importés).
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)  # 'rule.approve', 'review.validate'
    entity: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} {self.entity}:{self.entity_id}>"


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AppSetting {self.key}={self.value}>"
