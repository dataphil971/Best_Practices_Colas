"""Lot 7 — audit immuable

Revision ID: 0006_audit
Revises: 0005_integration
Create Date: 2026-03-20

Crée le journal d'audit technique global (immuable). La table app_settings a déjà
été créée au Lot 5 (0005) avec le seed retention_days=30.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_audit"
down_revision = "0005_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_audit_entity", "audit_log", ["entity", "entity_id"])
    op.create_index("idx_audit_user", "audit_log", ["user_id"])
    op.create_index("idx_audit_created", "audit_log", ["created_at"])

    # Immuabilité au niveau base : on interdit UPDATE et DELETE sur audit_log.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log est immuable : % interdit', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS forbid_audit_mutation();")
    op.drop_index("idx_audit_created", table_name="audit_log")
    op.drop_index("idx_audit_user", table_name="audit_log")
    op.drop_index("idx_audit_entity", table_name="audit_log")
    op.drop_table("audit_log")
