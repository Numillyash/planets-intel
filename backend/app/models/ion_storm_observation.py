from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IonStormObservation(Base):
    __tablename__ = "ion_storm_observations"

    __table_args__ = (
        Index("ix_ion_storm_observations_storm_id", "storm_id"),
    )

    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("private_observation_batches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    storm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    radius: Mapped[int | None] = mapped_column(Integer, nullable=True)
    voltage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warp: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    heading: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_growing: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
