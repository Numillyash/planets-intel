"""Add local ship order drafts.

Revision ID: 0011_ship_order_drafts
Revises: 0010_combat_state_observations
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_ship_order_drafts"
down_revision = "0010_combat_state_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ship_order_drafts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("linked_account_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("ship_id", sa.BigInteger(), nullable=False),
        sa.Column("base_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("base_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("warp", sa.SmallInteger(), nullable=True),
        sa.Column("waypoint_x", sa.Integer(), nullable=True),
        sa.Column("waypoint_y", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["linked_account_id"],
            ["planets_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["base_batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "linked_account_id",
            "game_id",
            "turn",
            "ship_id",
            name="uq_ship_order_draft_identity",
        ),
    )
    op.create_index(
        "ix_ship_order_drafts_game_turn_account",
        "ship_order_drafts",
        ["game_id", "turn", "linked_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ship_order_drafts_game_turn_account",
        table_name="ship_order_drafts",
    )
    op.drop_table("ship_order_drafts")
