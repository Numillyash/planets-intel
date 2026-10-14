"""Add observer-specific Planets.nu game activity observations.

Revision ID: 0015_game_activity
Revises: 0014_private_messages
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_game_activity"
down_revision = "0014_private_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_activity_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("observer_planets_account_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("activity_type", sa.Integer(), nullable=True),
        sa.Column("scope", sa.Integer(), nullable=True),
        sa.Column("turn", sa.Integer(), nullable=True),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("source_name", sa.String(length=512), nullable=True),
        sa.Column("source_type", sa.Integer(), nullable=True),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("target_name", sa.String(length=512), nullable=True),
        sa.Column("target_type", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("date_added", sa.String(length=64), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["observer_planets_account_id"],
            ["planets_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observer_planets_account_id",
            "game_id",
            "activity_id",
            name="uq_game_activity_observer_game_activity",
        ),
    )
    op.create_index(
        "ix_game_activity_observer_game_turn",
        "game_activity_observations",
        ["observer_planets_account_id", "game_id", "turn"],
        unique=False,
    )
    op.create_index(
        "ix_game_activity_observer_game_date",
        "game_activity_observations",
        ["observer_planets_account_id", "game_id", "date_added"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_game_activity_observer_game_date",
        table_name="game_activity_observations",
    )
    op.drop_index(
        "ix_game_activity_observer_game_turn",
        table_name="game_activity_observations",
    )
    op.drop_table("game_activity_observations")
