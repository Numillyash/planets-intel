from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CombatObservation(Base):
    """Observer-specific factual VCR/combat event from one private turn."""

    __tablename__ = "combat_observations"

    __table_args__ = (
        Index("ix_combat_observations_vcr", "vcr_id"),
        Index("ix_combat_observations_turn_position", "battle_turn", "x", "y"),
    )

    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("private_observation_batches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    vcr_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    battle_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    battle_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    y: Mapped[int | None] = mapped_column(Integer, nullable=True)

    left_owner_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    right_owner_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    left_object_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    right_object_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    left_is_starbase: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    right_is_starbase: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    left_hull_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    right_hull_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    left_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    right_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
