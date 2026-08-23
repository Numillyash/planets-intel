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
    op.add_column(
        "game_activity_observations",
        sa.Column("visibility_source", sa.String(length=32), nullable=True),
    )

    # Existing scope=3 records are the only historical rows for which the
    # current code already had an explicit private-message interpretation.
    # Do not invent provenance for every other historical row.
    op.execute(
        """
        UPDATE game_activity_observations
        SET visibility_source = 'private_activity'
        WHERE scope = 3
          AND activity_type = 1
          AND visibility_source IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("game_activity_observations", "visibility_source")
