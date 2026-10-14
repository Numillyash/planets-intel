"""Add public Commander Intelligence transport caches.

Revision ID: 0019_commander_intel_cache
Revises: 0018_tow_target_ship_id
Create Date: 2026-09-21 12:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0019_commander_intel_cache"
down_revision: str | None = "0018_tow_target_ship_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_player_history_cache",
        sa.Column("username_normalized", sa.String(length=255), nullable=False),
        sa.Column("status_filter", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "username_normalized",
            "status_filter",
        ),
    )
    op.create_index(
        "ix_public_player_history_cache_fetched_at",
        "public_player_history_cache",
        ["fetched_at"],
    )

    op.create_table(
        "public_game_info_cache",
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("game_id"),
    )
    op.create_index(
        "ix_public_game_info_cache_fetched_at",
        "public_game_info_cache",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_public_game_info_cache_fetched_at",
        table_name="public_game_info_cache",
    )
    op.drop_table("public_game_info_cache")

    op.drop_index(
        "ix_public_player_history_cache_fetched_at",
        table_name="public_player_history_cache",
    )
    op.drop_table("public_player_history_cache")
