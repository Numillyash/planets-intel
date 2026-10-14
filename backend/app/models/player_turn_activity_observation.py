from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlayerTurnActivityObservation(Base):
    """Observed public/private turn-state transition for one player slot."""

    __tablename__ = "player_turn_activity_observations"

    __table_args__ = (
        Index(
            "ix_player_turn_activity_game_turn_slot",
            "game_id",
            "turn",
            "slot_id",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    status_marker: Mapped[str | None] = mapped_column(String(8), nullable=True)
    turn_ready: Mapped[bool] = mapped_column(Boolean, nullable=False)
    turn_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    host_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
