"""Lot 5 — import intelligent et stockage pluggable

Revision ID: 0005_integration
Revises: 0004_validation
Create Date: 2026-03-15

Crée :
  - integration_config (connecteurs pluggables ; un seul actif par kind) ;
  - import_jobs (traçabilité des imports asynchrones) ;
  - app_settings (paramètres admin ; seed retention_days = 30).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_integration"
down_revision = "0004_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- integration_config ----------
    op.create_table(
        "integration_config",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("settings", postgresql.JSONB(),
                  server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('matching','storage','sharepoint')",
                           name="ck_integration_kind"),
    )
    # Un seul fournisseur actif par type (matching / storage / sharepoint).
    op.create_index("uniq_active_integration", "integration_config", ["kind"],
                    unique=True, postgresql_where=sa.text("is_active"))

    # ---------- import_jobs ----------
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("file_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source IN ('upload','sharepoint')", name="ck_import_source"),
        sa.CheckConstraint("status IN ('queued','running','done','failed')",
                           name="ck_import_status"),
    )
    op.create_index("idx_import_review", "import_jobs", ["review_id"])
    op.create_index("idx_import_status", "import_jobs", ["status"])

    # ---------- app_settings ----------
    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    # Valeur par défaut de rétention : 30 jours (modifiable par l'admin).
    op.execute("INSERT INTO app_settings(key, value) VALUES ('retention_days', '30')")


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index("idx_import_status", table_name="import_jobs")
    op.drop_index("idx_import_review", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("uniq_active_integration", table_name="integration_config")
    op.drop_table("integration_config")
