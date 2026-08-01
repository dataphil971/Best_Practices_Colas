"""Lot 4 — validation tierce : partage ciblé et validations

Revision ID: 0004_validation
Revises: 0003_reviews
Create Date: 2026-03-01

Crée :
  - share_links (token 256 bits, expiration, révocable) ;
  - share_targets (reviewers explicitement ciblés — clé composite) ;
  - validations (décision approved/rejected d'un reviewer) ;
  - validation_item_comments (commentaires par point de contrôle).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_validation"
down_revision = "0003_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- share_links ----------
    op.create_table(
        "share_links",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("token", name="uq_share_token"),
    )
    op.create_index("idx_share_review", "share_links", ["review_id"])
    # Index partiel : recherche rapide des liens actifs par token.
    op.create_index("idx_share_token", "share_links", ["token"],
                    postgresql_where=sa.text("NOT revoked"))

    # ---------- share_targets ----------
    op.create_table(
        "share_targets",
        sa.Column("share_link_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("share_links.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("idx_share_targets_reviewer", "share_targets", ["reviewer_id"])

    # ---------- validations ----------
    op.create_table(
        "validations",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("global_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("decision IN ('approved','rejected')",
                           name="ck_validation_decision"),
    )
    op.create_index("idx_validations_review", "validations", ["review_id"])

    # ---------- validation_item_comments ----------
    op.create_table(
        "validation_item_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("validation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("validations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_item_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("review_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
    )
    op.create_index("idx_vic_validation", "validation_item_comments", ["validation_id"])


def downgrade() -> None:
    op.drop_index("idx_vic_validation", table_name="validation_item_comments")
    op.drop_table("validation_item_comments")
    op.drop_index("idx_validations_review", table_name="validations")
    op.drop_table("validations")
    op.drop_index("idx_share_targets_reviewer", table_name="share_targets")
    op.drop_table("share_targets")
    op.drop_index("idx_share_token", table_name="share_links")
    op.drop_index("idx_share_review", table_name="share_links")
    op.drop_table("share_links")
