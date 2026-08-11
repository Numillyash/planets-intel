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


class PlanetObservation(Base):
    __tablename__ = "planet_observations"

    __table_args__ = (
        Index(
            "ix_planet_observations_planet_id",
            "planet_id",
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

    planet_id: Mapped[int] = mapped_column(
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

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
