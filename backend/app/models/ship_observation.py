from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShipObservation(Base):
    __tablename__ = "ship_observations"

    __table_args__ = (
        Index(
            "ix_ship_observations_ship_id",
            "ship_id",
        ),
    )

    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "private_observation_batches.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    ship_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    owner_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    info_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    hull_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    x: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    y: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    warp: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
