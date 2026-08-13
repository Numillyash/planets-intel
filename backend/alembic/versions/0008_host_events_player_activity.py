"""Add host events and player turn activity observations.

Revision ID: 0008_host_events_player_activity
Revises: 0007_game_rule_catalog
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_host_events_player_activity"
down_revision = "0007_game_rule_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "host_event_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("message_type", sa.Integer(), nullable=True),
        sa.Column("planet_id", sa.BigInteger(), nullable=True),
        sa.Column("starbase_id", sa.BigInteger(), nullable=True),
        sa.Column("x", sa.Integer(), nullable=True),
        sa.Column("y", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "event_key",
            name="uq_host_event_observation_batch_key",
        ),
    )
    op.create_index(
        "ix_host_event_observations_turn_type",
        "host_event_observations",
        ["turn", "event_type"],
        unique=False,
    )
    op.create_index(
        "ix_host_event_observations_planet",
        "host_event_observations",
        ["planet_id"],
        unique=False,
    )

    op.create_table(
        "player_turn_activity_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("status_marker", sa.String(length=8), nullable=True),
        sa.Column("turn_ready", sa.Boolean(), nullable=False),
        sa.Column("turn_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("host_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_player_turn_activity_game_turn_slot",
        "player_turn_activity_observations",
        ["game_id", "turn", "slot_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_player_turn_activity_game_turn_slot",
        table_name="player_turn_activity_observations",
    )
    op.drop_table("player_turn_activity_observations")

    op.drop_index(
        "ix_host_event_observations_planet",
        table_name="host_event_observations",
    )
    op.drop_index(
        "ix_host_event_observations_turn_type",
        table_name="host_event_observations",
    )
    op.drop_table("host_event_observations")
