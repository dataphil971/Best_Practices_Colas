"""Lot 3 — gestion des revues : reviews, review_items

Revision ID: 0003_reviews
Revises: 0002_referential
Create Date: 2026-02-15

Crée les tables des revues :
  - reviews (revue d'un livrable, score de conformité mis en cache) ;
  - review_items (points de contrôle ; chacun fige un rule_version_id précis).

Les types review_status / item_status / progress_state sont créés ici.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_reviews"
down_revision = "0002_referential"
branch_labels = None
depends_on = None


def upgrade() -> None:
    review_status = postgresql.ENUM(
        "draft", "in_progress", "submitted", "validated", "changes_requested",
        name="review_status", create_type=True,
    )
    item_status = postgresql.ENUM(
        "ok", "ko", "partial", "na", "unset", name="item_status", create_type=True,
    )
    progress_state = postgresql.ENUM(
        "todo", "in_progress", "done", name="progress_state", create_type=True,
    )
    review_status.create(op.get_bind(), checkfirst=True)
    item_status.create(op.get_bind(), checkfirst=True)
    progress_state.create(op.get_bind(), checkfirst=True)

    review_status_ref = postgresql.ENUM(name="review_status", create_type=False)
    item_status_ref = postgresql.ENUM(name="item_status", create_type=False)
    progress_ref = postgresql.ENUM(name="progress_state", create_type=False)
    checklist_ref = postgresql.ENUM(name="checklist_type", create_type=False)

    # ---------- reviews ----------
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("report_name", sa.Text(), nullable=False),
        sa.Column("checklist_type", checklist_ref, nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", review_status_ref,
                  server_default=sa.text("'in_progress'"), nullable=False),
        sa.Column("compliance_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_reviews_author", "reviews", ["author_id"])
    op.create_index("idx_reviews_status", "reviews", ["status"])

    # ---------- review_items ----------
    op.create_table(
        "review_items",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("rule_versions.id"), nullable=False),
        sa.Column("status", item_status_ref,
                  server_default=sa.text("'unset'"), nullable=False),
        sa.Column("progress", progress_ref,
                  server_default=sa.text("'todo'"), nullable=False),
        sa.Column("comment", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("risk", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("risk_comment", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("proposed_solution", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("estimated_days", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("definition_of_done", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("priority", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("responsible", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("last_update", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_items_review", "review_items", ["review_id"])


def downgrade() -> None:
    op.drop_index("idx_items_review", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index("idx_reviews_status", table_name="reviews")
    op.drop_index("idx_reviews_author", table_name="reviews")
    op.drop_table("reviews")
    op.execute("DROP TYPE IF EXISTS progress_state;")
    op.execute("DROP TYPE IF EXISTS item_status;")
    op.execute("DROP TYPE IF EXISTS review_status;")
