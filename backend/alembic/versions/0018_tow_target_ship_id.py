"""Add explicit Tow target to ship order drafts.

Revision ID: 0018_tow_target_ship_id
Revises: 0017_outgoing_msg_recipients
Create Date: 2026-09-07 00:42:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision = "0018_tow_target_ship_id"
down_revision: str | None = "0017_outgoing_msg_recipients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ship_order_drafts",
        sa.Column("tow_target_ship_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ship_order_drafts", "tow_target_ship_id")
