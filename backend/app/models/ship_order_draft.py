from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShipOrderDraft(Base):
    __tablename__ = "ship_order_drafts"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "linked_account_id",
            "game_id",
            "turn",
            "ship_id",
            name="uq_ship_order_draft_identity",
        ),
        Index(
            "ix_ship_order_drafts_game_turn_account",
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
    ship_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Snapshot provenance. Draft values are never canonical observations.
    base_batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("private_observation_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    warp: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    waypoint_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    waypoint_y: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
