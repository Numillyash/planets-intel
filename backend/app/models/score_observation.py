from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScoreObservation(Base):
    __tablename__ = "score_observations"

    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "turn",
            "slot_id",
            "source",
            name="uq_score_observation_source",
        ),
        Index(
            "ix_score_observations_game_turn",
            "game_id",
            "turn",
        ),
        Index(
            "ix_score_observations_game_slot_turn",
            "game_id",
            "slot_id",
            "turn",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "games.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    slot_id: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source_date_added: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    capital_ships: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    freighters: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    planets: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    starbases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    military_score: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    inventory_score: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    priority_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    military_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
    )

    victory_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    victory_bonuses: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    technological_accumulator: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    widest_reach: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    greatest_warrior: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    happy_beings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
