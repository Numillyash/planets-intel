"""Add ion storm observation storage.

Revision ID: 0004_ion_storm_observations
Revises: 0003_private_observations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_ion_storm_observations"
down_revision = "0003_private_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ion_storm_observations",
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("storm_id", sa.BigInteger(), nullable=False),
        sa.Column("x", sa.Integer(), nullable=True),
        sa.Column("y", sa.Integer(), nullable=True),
        sa.Column("radius", sa.Integer(), nullable=True),
        sa.Column("voltage", sa.Integer(), nullable=True),
        sa.Column("warp", sa.SmallInteger(), nullable=True),
        sa.Column("heading", sa.Integer(), nullable=True),
        sa.Column("is_growing", sa.Boolean(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("batch_id", "storm_id"),
    )
    op.create_index(
        "ix_ion_storm_observations_storm_id",
        "ion_storm_observations",
        ["storm_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ion_storm_observations_storm_id",
        table_name="ion_storm_observations",
    )
    op.drop_table("ion_storm_observations")
