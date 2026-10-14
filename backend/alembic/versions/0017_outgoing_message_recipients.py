"""Preserve factual recipients for IntelBoard-originated messages.

Revision ID: 0017_outgoing_msg_recipients
Revises: 0016_activity_provenance
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_outgoing_msg_recipients"
down_revision = "0016_activity_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "game_activity_observations",
        sa.Column("outgoing_recipient_player_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(
        "game_activity_observations",
        "outgoing_recipient_player_ids",
    )
