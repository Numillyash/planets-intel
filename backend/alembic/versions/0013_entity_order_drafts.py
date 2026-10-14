"""Add ship mission/FC drafts plus planet and starbase order drafts.

Revision ID: 0013_entity_order_drafts
Revises: 0012_intercept_order_drafts
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_entity_order_drafts"
down_revision = "0012_intercept_order_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ship_order_drafts",
        sa.Column("friendly_code", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "ship_order_drafts",
        sa.Column("mission", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "ship_order_drafts",
        sa.Column("primary_enemy_id", sa.SmallInteger(), nullable=True),
    )

    op.create_table(
        "planet_order_drafts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("linked_account_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("planet_id", sa.BigInteger(), nullable=False),
        sa.Column("base_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("base_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("friendly_code", sa.String(length=3), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["linked_account_id"],
            ["planets_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["base_batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "linked_account_id",
            "game_id",
            "turn",
            "planet_id",
            name="uq_planet_order_draft_identity",
        ),
    )
    op.create_index(
        "ix_planet_order_drafts_game_turn_account",
        "planet_order_drafts",
        ["game_id", "turn", "linked_account_id"],
        unique=False,
    )

    op.create_table(
        "starbase_order_drafts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("linked_account_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("starbase_id", sa.BigInteger(), nullable=False),
        sa.Column("planet_id", sa.BigInteger(), nullable=False),
        sa.Column("base_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("base_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "primary_order",
            sa.String(length=32),
            server_default="none",
            nullable=False,
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
            "primary_order IN ('none', 'refuel', 'max_defense', 'load_torpedoes', "
            "'unload_freighters', 'repair_base', 'force_surrender')",
            name="ck_starbase_order_drafts_primary_order",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["linked_account_id"],
            ["planets_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["base_batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "linked_account_id",
            "game_id",
            "turn",
            "starbase_id",
            name="uq_starbase_order_draft_identity",
        ),
    )
    op.create_index(
        "ix_starbase_order_drafts_game_turn_account",
        "starbase_order_drafts",
        ["game_id", "turn", "linked_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_starbase_order_drafts_game_turn_account",
        table_name="starbase_order_drafts",
    )
    op.drop_table("starbase_order_drafts")
    op.drop_index(
        "ix_planet_order_drafts_game_turn_account",
        table_name="planet_order_drafts",
    )
    op.drop_table("planet_order_drafts")
    op.drop_column("ship_order_drafts", "primary_enemy_id")
    op.drop_column("ship_order_drafts", "mission")
    op.drop_column("ship_order_drafts", "friendly_code")
