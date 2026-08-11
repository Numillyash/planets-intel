from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StarbaseObservation(Base):
    __tablename__ = "starbase_observations"

    __table_args__ = (
        Index(
            "ix_starbase_observations_starbase_id",
            "starbase_id",
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

    starbase_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    planet_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    race_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    info_turn: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
