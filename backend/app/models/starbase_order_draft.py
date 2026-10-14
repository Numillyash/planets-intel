from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StarbaseOrderDraft(Base):
    __tablename__ = "starbase_order_drafts"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "linked_account_id",
            "game_id",
            "turn",
            "starbase_id",
            name="uq_starbase_order_draft_identity",
        ),
        CheckConstraint(
            "primary_order IN ('none', 'refuel', 'max_defense', 'load_torpedoes', "
            "'unload_freighters', 'repair_base', 'force_surrender')",
            name="ck_starbase_order_drafts_primary_order",
        ),
        Index(
            "ix_starbase_order_drafts_game_turn_account",
            "game_id",
            "turn",
            "linked_account_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    linked_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("planets_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    starbase_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    planet_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    base_batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("private_observation_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    primary_order: Mapped[str] = mapped_column(
        String(32),
        server_default="none",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
