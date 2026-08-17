"""Lot 8 — import des résultats Agent BI

Revision ID: 0007_agent_results
Revises: 0006_audit
Create Date: 2026-08-18

Ajoute le pont entre le référentiel de règles PR Review et le moteur
déterministe Agent_BI/03_PYTHON :

  - `rules.code` : identifiant technique stable et immuable (ex. "BP-22"),
    absent du modèle jusqu'ici (le référentiel ne connaissait que des UUID).
    C'est ce qui permet de retrouver un `review_item` à partir d'un
    `rule_id` Agent BI sans rapprochement fragile sur le texte.

  - `review_items.last_update_source` : distingue un statut saisi par un
    humain d'un statut appliqué par l'agent. Sans cette colonne, un import
    agent écraserait silencieusement un jugement humain déjà saisi — ce que
    le principe directeur d'Agent BI interdit explicitement (« l'agent ne
    décide pas à la place du relecteur »).

  - `review_items.agent_evidence` : preuve complète (Rule ID / Object /
    Expected / Actual / Evidence) renvoyée par Agent BI pour l'item,
    conservée telle quelle pour audit.

  - `review_items.agent_fingerprint` : empreinte du projet PBIP analysé
    (cf. `project.fingerprint` du contrat JSON Agent BI), utilisée pour une
    idempotence naturelle : réappliquer le même résultat sur le même état
    de projet est un no-op plutôt qu'une réécriture inutile.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_agent_results"
down_revision = "0006_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rules", sa.Column("code", sa.String(), nullable=True))
    op.create_index(
        "uq_rules_code", "rules", ["code"], unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )

    op.add_column(
        "review_items",
        sa.Column(
            "last_update_source", sa.String(), nullable=False,
            server_default="unset",
        ),
    )
    op.create_check_constraint(
        "ck_review_items_update_source",
        "review_items",
        "last_update_source IN ('unset','human','agent')",
    )
    op.add_column(
        "review_items",
        sa.Column("agent_evidence", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "review_items",
        sa.Column("agent_fingerprint", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_items", "agent_fingerprint")
    op.drop_column("review_items", "agent_evidence")
    op.drop_constraint("ck_review_items_update_source", "review_items", type_="check")
    op.drop_column("review_items", "last_update_source")
    op.drop_index("uq_rules_code", table_name="rules")
    op.drop_column("rules", "code")
