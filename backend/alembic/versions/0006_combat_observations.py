"""Add observer-specific combat/VCR observations.

Revision ID: 0006_combat_observations
Revises: 0005_stellar_cartography
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_combat_observations"
down_revision = "0005_stellar_cartography"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "combat_observations",
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("vcr_id", sa.BigInteger(), nullable=False),
        sa.Column("battle_turn", sa.Integer(), nullable=False),
        sa.Column("battle_type", sa.Integer(), nullable=True),
        sa.Column("x", sa.Integer(), nullable=True),
        sa.Column("y", sa.Integer(), nullable=True),
        sa.Column("left_owner_id", sa.SmallInteger(), nullable=True),
        sa.Column("right_owner_id", sa.SmallInteger(), nullable=True),
        sa.Column("left_object_id", sa.BigInteger(), nullable=True),
        sa.Column("right_object_id", sa.BigInteger(), nullable=True),
        sa.Column("left_is_starbase", sa.Boolean(), nullable=True),
        sa.Column("right_is_starbase", sa.Boolean(), nullable=True),
        sa.Column("left_hull_id", sa.Integer(), nullable=True),
        sa.Column("right_hull_id", sa.Integer(), nullable=True),
        sa.Column("left_name", sa.String(length=255), nullable=True),
        sa.Column("right_name", sa.String(length=255), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("batch_id", "vcr_id"),
    )

    op.create_index(
        "ix_combat_observations_vcr",
        "combat_observations",
        ["vcr_id"],
    )
    op.create_index(
        "ix_combat_observations_turn_position",
        "combat_observations",
        ["battle_turn", "x", "y"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_combat_observations_turn_position",
        table_name="combat_observations",
    )
    op.drop_index(
        "ix_combat_observations_vcr",
        table_name="combat_observations",
    )
    op.drop_table("combat_observations")
