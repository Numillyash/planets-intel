from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PrivateMessageObservation(Base):
    """Raw observer-specific Planets.nu message record from private turn data."""

    __tablename__ = "private_message_observations"

    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "source_collection",
            "message_key",
            name="uq_private_message_observation_batch_source_key",
        ),
        Index(
            "ix_private_message_observations_batch_turn",
            "batch_id",
            "message_turn",
        ),
        Index(
            "ix_private_message_observations_message_id",
            "message_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("private_observation_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_collection: Mapped[str] = mapped_column(String(32), nullable=False)
    message_key: Mapped[str] = mapped_column(String(128), nullable=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
