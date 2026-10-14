"""Add dashboard intel sharing agreements.

Revision ID: 0004_dashboard_intel_sharing
Revises: 0003_private_observations
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_dashboard_intel_sharing"
down_revision = "0003_private_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_intel_shares",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "account_low_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "account_high_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "requested_by_account_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "approved_low_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "approved_high_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_low_id < account_high_id",
            name="ck_dashboard_intel_share_account_order",
        ),
        sa.ForeignKeyConstraint(
            ["account_low_id"],
            ["planets_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_high_id"],
            ["planets_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_account_id"],
            ["planets_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_low_id",
            "account_high_id",
            name="uq_dashboard_intel_share_pair",
        ),
    )

    op.create_index(
        "ix_dashboard_intel_shares_low",
        "dashboard_intel_shares",
        ["account_low_id"],
    )
    op.create_index(
        "ix_dashboard_intel_shares_high",
        "dashboard_intel_shares",
        ["account_high_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dashboard_intel_shares_high",
        table_name="dashboard_intel_shares",
    )
    op.drop_index(
        "ix_dashboard_intel_shares_low",
        table_name="dashboard_intel_shares",
    )
    op.drop_table("dashboard_intel_shares")
