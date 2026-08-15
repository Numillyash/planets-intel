"""Add raw observer-specific private message observations.

Revision ID: 0014_private_messages
Revises: 0013_entity_order_drafts
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_private_messages"
down_revision = "0013_entity_order_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "private_message_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("source_collection", sa.String(length=32), nullable=False),
        sa.Column("message_key", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("message_type", sa.Integer(), nullable=True),
        sa.Column("message_turn", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("headline", sa.String(length=512), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("x", sa.Integer(), nullable=True),
        sa.Column("y", sa.Integer(), nullable=True),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "source_collection",
            "message_key",
            name="uq_private_message_observation_batch_source_key",
        ),
    )
    op.create_index(
        "ix_private_message_observations_batch_turn",
        "private_message_observations",
        ["batch_id", "message_turn"],
        unique=False,
    )
    op.create_index(
        "ix_private_message_observations_message_id",
        "private_message_observations",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_private_message_observations_message_id",
        table_name="private_message_observations",
    )
    op.drop_index(
        "ix_private_message_observations_batch_turn",
        table_name="private_message_observations",
    )
    op.drop_table("private_message_observations")
