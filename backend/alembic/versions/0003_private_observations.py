"""Add private turn observation storage.

Revision ID: 0003_private_observations
Revises: 0002_users_and_planets_accounts
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_private_observations"
down_revision = "0002_users_and_planets_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "private_observation_batches",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "turn",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "observer_planets_account_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "source_player_slot_id",
            sa.SmallInteger(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "snapshot_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["observer_planets_account_id"],
            ["planets_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "source_player_slot_id"],
            [
                "game_player_slots.game_id",
                "game_player_slots.slot_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "turn",
            "observer_planets_account_id",
            "source",
            "snapshot_hash",
            name="uq_private_observation_snapshot",
        ),
    )

    op.create_index(
        "ix_private_observation_batches_game_turn",
        "private_observation_batches",
        ["game_id", "turn"],
    )

    op.create_index(
        "ix_private_observation_batches_observer_game_turn",
        "private_observation_batches",
        [
            "observer_planets_account_id",
            "game_id",
            "turn",
        ],
    )

    op.create_table(
        "planet_observations",
        sa.Column(
            "batch_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "planet_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "info_turn",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "x",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "y",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "batch_id",
            "planet_id",
        ),
    )

    op.create_index(
        "ix_planet_observations_planet_id",
        "planet_observations",
        ["planet_id"],
    )

    op.create_table(
        "ship_observations",
        sa.Column(
            "batch_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "ship_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "info_turn",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "hull_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "x",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "y",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "warp",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "batch_id",
            "ship_id",
        ),
    )

    op.create_index(
        "ix_ship_observations_ship_id",
        "ship_observations",
        ["ship_id"],
    )

    op.create_table(
        "starbase_observations",
        sa.Column(
            "batch_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "starbase_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "planet_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "race_id",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "info_turn",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["private_observation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "batch_id",
            "starbase_id",
        ),
    )

    op.create_index(
        "ix_starbase_observations_starbase_id",
        "starbase_observations",
        ["starbase_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_starbase_observations_starbase_id",
        table_name="starbase_observations",
    )
    op.drop_table("starbase_observations")

    op.drop_index(
        "ix_ship_observations_ship_id",
        table_name="ship_observations",
    )
    op.drop_table("ship_observations")

    op.drop_index(
        "ix_planet_observations_planet_id",
        table_name="planet_observations",
    )
    op.drop_table("planet_observations")

    op.drop_index(
        "ix_private_observation_batches_observer_game_turn",
        table_name="private_observation_batches",
    )
    op.drop_index(
        "ix_private_observation_batches_game_turn",
        table_name="private_observation_batches",
    )
    op.drop_table("private_observation_batches")
