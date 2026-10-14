"""Add semantic intercept targets to local ship order drafts.

Revision ID: 0012_intercept_order_drafts
Revises: 0011_ship_order_drafts
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_intercept_order_drafts"
down_revision = "0011_ship_order_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ship_order_drafts",
        sa.Column(
            "movement_mode",
            sa.String(length=16),
            server_default="waypoint",
            nullable=False,
        ),
    )
    op.add_column(
        "ship_order_drafts",
        sa.Column("intercept_target_ship_id", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_ship_order_drafts_movement_mode",
        "ship_order_drafts",
        "movement_mode IN ('waypoint', 'intercept')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ship_order_drafts_movement_mode",
        "ship_order_drafts",
        type_="check",
    )
    op.drop_column("ship_order_drafts", "intercept_target_ship_id")
    op.drop_column("ship_order_drafts", "movement_mode")
