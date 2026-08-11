from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PrivateObservationBatch(Base):
    __tablename__ = "private_observation_batches"

    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "source_player_slot_id"],
            [
                "game_player_slots.game_id",
                "game_player_slots.slot_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "game_id",
            "turn",
            "observer_planets_account_id",
            "source",
            "snapshot_hash",
            name="uq_private_observation_snapshot",
        ),
        Index(
            "ix_private_observation_batches_game_turn",
            "game_id",
            "turn",
        ),
        Index(
            "ix_private_observation_batches_observer_game_turn",
            "observer_planets_account_id",
            "game_id",
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

    observer_planets_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "planets_accounts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    source_player_slot_id: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    snapshot_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
