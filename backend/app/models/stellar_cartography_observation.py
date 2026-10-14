from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StellarCartographyObservation(Base):
    """Observer-specific factual terrain from a private Planets.nu turn."""

    __tablename__ = "stellar_cartography_observations"

    __table_args__ = (
        Index(
            "ix_stellar_cartography_feature",
            "feature_type",
            "feature_id",
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

    feature_type: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    feature_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    info_turn: Mapped[int | None] = mapped_column(
        Integer,
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

    radius: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
