from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CombatStateObservation(Base):
    __tablename__ = "combat_state_observations"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "game_id",
            "turn",
            "vcr_id",
            "ship_id",
            name="uq_combat_state_observation_identity",
        ),
        Index(
            "ix_combat_state_observation_game_turn_ship",
            "game_id",
            "turn",
            "ship_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    vcr_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ship_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    post_combat_torpedoes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_combat_fighters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
