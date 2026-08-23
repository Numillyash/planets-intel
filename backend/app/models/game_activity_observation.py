from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GameActivityObservation(Base):
    """Observer-specific raw Planets.nu in-game activity record.

    The activity feed can contain public discussions, private correspondence,
    diplomacy notices, and game/system events. The raw payload is preserved and
    ``visibility_source`` records which factual Planets.nu activity endpoint or
    explicit IntelBoard write exposed the row, so read-side semantics do not
    have to infer privacy from target-field shape alone.
    """

    __tablename__ = "game_activity_observations"

    __table_args__ = (
        UniqueConstraint(
            "observer_planets_account_id",
            "game_id",
            "activity_id",
            name="uq_game_activity_observer_game_activity",
        ),
        Index(
            "ix_game_activity_observer_game_turn",
            "observer_planets_account_id",
            "game_id",
            "turn",
        ),
        Index(
            "ix_game_activity_observer_game_date",
            "observer_planets_account_id",
            "game_id",
            "date_added",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    observer_planets_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("planets_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    activity_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scope: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outgoing_recipient_player_ids: Mapped[list[int] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_added: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
