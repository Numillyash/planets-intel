"""Preserve Planets.nu activity endpoint provenance.

Revision ID: 0016_activity_provenance
Revises: 0015_game_activity
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_activity_provenance"
down_revision = "0015_game_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical rows predate endpoint provenance persistence. Keep them NULL:
    # deriving an endpoint name from scope/target shape would turn an inference
    # into a fabricated fact. Normal refreshes populate provenance only when an
    # activity is actually observed through the corresponding endpoint.
    op.add_column(
        "game_activity_observations",
        sa.Column("visibility_source", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_activity_observations", "visibility_source")
