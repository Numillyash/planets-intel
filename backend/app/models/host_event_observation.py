from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HostEventObservation(Base):
    """Observer-specific factual host/system event derived from safe message metadata."""

    __tablename__ = "host_event_observations"

    __table_args__ = (
        Index("ix_host_event_observations_turn_type", "turn", "event_type"),
        Index("ix_host_event_observations_planet", "planet_id"),
        Index("ix_host_event_observations_ship", "ship_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("private_observation_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planet_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    starbase_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ship_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ship_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
