from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GamePlayerSlot(Base):
    __tablename__ = "game_player_slots"

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "games.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    slot_id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
    )

    account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    race_id: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    first_seen_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    last_seen_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
