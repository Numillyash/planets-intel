"""Game-scoped intel consent ledger (not an authorization migration).

Revision ID: 0020_game_scoped_intel_grants
Revises: 0019_commander_intel_cache
Create Date: 2026-10-14
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_game_scoped_intel_grants"
down_revision: str | None = "0019_commander_intel_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_intel_grants",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantor_account_id", sa.BigInteger(), sa.ForeignKey("planets_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantee_account_id", sa.BigInteger(), sa.ForeignKey("planets_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantor_slot_id", sa.SmallInteger(), nullable=False),
        sa.Column("grantee_slot_id", sa.SmallInteger(), nullable=False),
        sa.Column("membership_verified_turn", sa.Integer(), nullable=False),
        sa.Column("requested_scopes", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("grantor_account_id <> grantee_account_id", name="ck_game_intel_grant_distinct_accounts"),
        sa.CheckConstraint("status IN ('pending', 'consented_pending_policy', 'revoked')", name="ck_game_intel_grant_status"),
    )
    op.create_index("ix_game_intel_grant_grantor", "game_intel_grants", ["grantor_account_id", "game_id"])
    op.create_index("ix_game_intel_grant_grantee", "game_intel_grants", ["grantee_account_id", "game_id"])
    op.create_index(
        "uq_game_intel_grant_unrevoked", "game_intel_grants",
        ["game_id", "grantor_account_id", "grantee_account_id"],
        unique=True, postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_game_intel_grant_unrevoked", table_name="game_intel_grants")
    op.drop_index("ix_game_intel_grant_grantee", table_name="game_intel_grants")
    op.drop_index("ix_game_intel_grant_grantor", table_name="game_intel_grants")
    op.drop_table("game_intel_grants")
