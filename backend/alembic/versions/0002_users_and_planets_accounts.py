"""Add local users, sessions and linked Planets.nu accounts.

Revision ID: 0002_users_and_planets_accounts
Revises: 0001_public_intel
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_users_and_planets_accounts"
down_revision = "0001_public_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "username",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "display_name",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
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
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "app_sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )

    op.create_index(
        "ix_app_sessions_user_id",
        "app_sessions",
        ["user_id"],
    )

    op.create_index(
        "ix_app_sessions_expires_at",
        "app_sessions",
        ["expires_at"],
    )

    op.create_table(
        "planets_accounts",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "planets_username",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "planets_username_normalized",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "planets_account_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "api_key_encrypted",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "planets_username_normalized",
            name="uq_planets_account_user_username",
        ),
    )


def downgrade() -> None:
    op.drop_table("planets_accounts")

    op.drop_index(
        "ix_app_sessions_expires_at",
        table_name="app_sessions",
    )

    op.drop_index(
        "ix_app_sessions_user_id",
        table_name="app_sessions",
    )

    op.drop_table("app_sessions")
    op.drop_table("app_users")
