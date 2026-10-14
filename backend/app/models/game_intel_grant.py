"""Game-scoped, directional consent evidence. NEVER direct read authority."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, SmallInteger, String, text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GameIntelGrant(Base):
    __tablename__ = "game_intel_grants"
    __table_args__ = (
        Index("ix_game_intel_grant_grantor", "grantor_account_id", "game_id"),
        Index("ix_game_intel_grant_grantee", "grantee_account_id", "game_id"),
        Index(
            "uq_game_intel_grant_unrevoked",
            "game_id", "grantor_account_id", "grantee_account_id",
            unique=True, postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    grantor_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("planets_accounts.id", ondelete="CASCADE"), nullable=False)
    grantee_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("planets_accounts.id", ondelete="CASCADE"), nullable=False)
    grantor_slot_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    grantee_slot_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    membership_verified_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
