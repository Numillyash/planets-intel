"""Add observer-specific stellar cartography observations.

Revision ID: 0005_stellar_cartography
Revises: 0004_dashboard_intel_sharing
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_stellar_cartography"
down_revision = "0004_dashboard_intel_sharing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stellar_cartography_observations",
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_type", sa.String(length=32), nullable=False),
        sa.Column("feature_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("info_turn", sa.Integer(), nullable=True),
        sa.Column("x", sa.Integer(), nullable=True),
        sa.Column("y", sa.Integer(), nullable=True),
        sa.Column("radius", sa.Integer(), nullable=True),
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
        sa.PrimaryKeyConstraint(
            "batch_id",
            "feature_type",
            "feature_id",
        ),
    )

    op.create_index(
        "ix_stellar_cartography_feature",
        "stellar_cartography_observations",
        ["feature_type", "feature_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stellar_cartography_feature",
        table_name="stellar_cartography_observations",
    )
    op.drop_table("stellar_cartography_observations")
