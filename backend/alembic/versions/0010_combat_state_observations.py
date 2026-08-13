"""Add post-combat state observations.

Revision ID: 0010_combat_state_observations
Revises: 0009_host_event_actor_fields
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_combat_state_observations"
down_revision = "0009_host_event_actor_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "combat_state_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("vcr_id", sa.Integer(), nullable=False),
        sa.Column("ship_id", sa.BigInteger(), nullable=False),
        sa.Column("post_combat_torpedoes", sa.Integer(), nullable=True),
        sa.Column("post_combat_fighters", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "game_id", "turn", "vcr_id", "ship_id",
            name="uq_combat_state_observation_identity",
        ),
    )
    op.create_index(
        "ix_combat_state_observation_game_turn_ship",
        "combat_state_observations",
        ["game_id", "turn", "ship_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_combat_state_observation_game_turn_ship",
        table_name="combat_state_observations",
    )
    op.drop_table("combat_state_observations")
