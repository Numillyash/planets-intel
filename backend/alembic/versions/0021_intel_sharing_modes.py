"""Record native-vs-unrestricted game-scoped consent intent, without granting access.

Revision ID: 0021_intel_sharing_modes
Revises: 0020_game_scoped_intel_grants
Create Date: 2026-10-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0021_intel_sharing_modes"
down_revision: str | None = "0020_game_scoped_intel_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "game_intel_grants",
        sa.Column("sharing_mode", sa.String(length=24), nullable=False, server_default="native"),
    )
    op.add_column(
        "game_intel_grants",
        sa.Column("expanded_disclosure_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_game_intel_grant_sharing_mode",
        "game_intel_grants",
        "sharing_mode IN ('native', 'unrestricted')",
    )
    # Existing P1 records stay native and never receive retroactive expanded consent.
    op.alter_column("game_intel_grants", "sharing_mode", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_game_intel_grant_sharing_mode", "game_intel_grants", type_="check",
    )
    op.drop_column("game_intel_grants", "expanded_disclosure_confirmed_at")
    op.drop_column("game_intel_grants", "sharing_mode")
