"""
Modèles ORM de l'import intelligent et des intégrations (Lot 5).

  - `IntegrationConfig` : configuration pluggable des connecteurs (matching / storage
    / sharepoint). Un seul `is_active` par `kind` — c'est ce qui permet à l'admin de
    BASCULER de fournisseur d'IA ou de stockage à chaud, sans redéploiement. Les
    SECRETS n'y sont jamais stockés : seule une référence (`secret_ref`) vers le
    coffre à secrets est conservée.

  - `ImportJob` : traçabilité d'un import asynchrone (upload ou SharePoint). Porte
    le statut (queued/running/done/failed) et le résultat de matching.
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
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IntegrationConfig(Base):
    __tablename__ = "integration_config"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('matching','storage','sharepoint')", name="ck_integration_kind"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)  # matching|storage|sharepoint
    provider: Mapped[str] = mapped_column(String, nullable=False)
    # Paramètres non sensibles : endpoints, régions, buckets, patterns. JAMAIS de secret.
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Référence vers le coffre à secrets (Key Vault) — jamais la valeur du secret.
    secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IntegrationConfig {self.kind}:{self.provider} active={self.is_active}>"


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint("source IN ('upload','sharepoint')", name="ck_import_source"),
        CheckConstraint(
            "status IN ('queued','running','done','failed')", name="ck_import_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String, nullable=False)  # upload|sharepoint
    file_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # clé stockage
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    # {matched, ambiguous, filled, total, details[]}
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImportJob {self.id} {self.status}>"
