"""Add structured actor fields to host events.

Revision ID: 0009_host_event_actor_fields
Revises: 0008_host_events_player_activity
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_host_event_actor_fields"
down_revision = "0008_host_events_player_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("host_event_observations", sa.Column("ship_id", sa.BigInteger(), nullable=True))
    op.add_column("host_event_observations", sa.Column("ship_name", sa.String(length=255), nullable=True))
    op.create_index("ix_host_event_observations_ship", "host_event_observations", ["ship_id"], unique=False)


def downgrade() -> None:
    pass
