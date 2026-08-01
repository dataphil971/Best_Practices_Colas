"""Lot 2 — référentiel versionné : categories, rules, rule_versions, rule_activity

Revision ID: 0002_referential
Revises: 0001_initial_users
Create Date: 2026-02-01

Crée le socle du référentiel avec versionnement immuable :
  - types enum checklist_type / criticality / lifecycle_state ;
  - table categories (unicité par référentiel) ;
  - table rules (identité stable) ;
  - table rule_versions (contenu immuable, une seule version courante par règle) ;
  - table rule_activity (journal d'activité admin, attribution multi-admins).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_referential"
down_revision = "0001_initial_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extension pour la recherche floue (fallback matching, Lot 5).
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    checklist_type = postgresql.ENUM(
        "powerbi", "appbi", "build", name="checklist_type", create_type=True
    )
    criticality = postgresql.ENUM(
        "blocking", "recommended", "optional", name="criticality", create_type=True
    )
    lifecycle_state = postgresql.ENUM(
        "pending", "approved", "rejected", name="lifecycle_state", create_type=True
    )
    checklist_type.create(op.get_bind(), checkfirst=True)
    criticality.create(op.get_bind(), checkfirst=True)
    lifecycle_state.create(op.get_bind(), checkfirst=True)

    # Réutilise les types déjà présents en base sans tenter de les recréer.
    checklist_ref = postgresql.ENUM(name="checklist_type", create_type=False)
    criticality_ref = postgresql.ENUM(name="criticality", create_type=False)
    lifecycle_ref = postgresql.ENUM(name="lifecycle_state", create_type=False)

    # ---------- categories ----------
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("checklist_type", checklist_ref, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.UniqueConstraint("checklist_type", "name", name="uq_category_type_name"),
    )
    op.create_index("idx_categories_type", "categories", ["checklist_type"])

    # ---------- rules ----------
    op.create_table(
        "rules",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("checklist_type", checklist_ref, nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','retired')", name="ck_rules_status"),
    )
    op.create_index("idx_rules_type", "rules", ["checklist_type"])
    op.create_index("idx_rules_category", "rules", ["category_id"])

    # ---------- rule_versions ----------
    op.create_table(
        "rule_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("subs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("criticality", criticality_ref,
                  server_default=sa.text("'recommended'"), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("lifecycle", lifecycle_ref,
                  server_default=sa.text("'pending'"), nullable=False),
        sa.Column("proposed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("rule_id", "version_number", name="uq_rule_version_number"),
    )
    op.create_index("idx_rv_rule", "rule_versions", ["rule_id"])
    # Une seule version courante par règle (index unique partiel).
    op.create_index("uniq_current_version", "rule_versions", ["rule_id"],
                    unique=True, postgresql_where=sa.text("is_current"))
    op.create_index("idx_rv_lifecycle", "rule_versions", ["lifecycle"],
                    postgresql_where=sa.text("is_current"))
    # Recherche floue sur le texte (fallback du matching, Lot 5).
    op.execute(
        "CREATE INDEX idx_rv_text_trgm ON rule_versions "
        "USING gin (text gin_trgm_ops);"
    )

    # ---------- rule_activity ----------
    op.create_table(
        "rule_activity",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rule_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("checklist_type", checklist_ref, nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "action IN ('rule_created','rule_proposed','rule_revised',"
            "'rule_approved','rule_rejected','rule_retired','rule_restored')",
            name="ck_activity_action",
        ),
    )
    op.create_index("idx_activity_type", "rule_activity",
                    ["checklist_type", sa.text("created_at DESC")])
    op.create_index("idx_activity_rule", "rule_activity", ["rule_id"])
    op.create_index("idx_activity_actor", "rule_activity", ["actor_id"])


def downgrade() -> None:
    op.drop_index("idx_activity_actor", table_name="rule_activity")
    op.drop_index("idx_activity_rule", table_name="rule_activity")
    op.drop_index("idx_activity_type", table_name="rule_activity")
    op.drop_table("rule_activity")

    op.execute("DROP INDEX IF EXISTS idx_rv_text_trgm;")
    op.drop_index("idx_rv_lifecycle", table_name="rule_versions")
    op.drop_index("uniq_current_version", table_name="rule_versions")
    op.drop_index("idx_rv_rule", table_name="rule_versions")
    op.drop_table("rule_versions")

    op.drop_index("idx_rules_category", table_name="rules")
    op.drop_index("idx_rules_type", table_name="rules")
    op.drop_table("rules")

    op.drop_index("idx_categories_type", table_name="categories")
    op.drop_table("categories")

    op.execute("DROP TYPE IF EXISTS lifecycle_state;")
    op.execute("DROP TYPE IF EXISTS criticality;")
    op.execute("DROP TYPE IF EXISTS checklist_type;")
