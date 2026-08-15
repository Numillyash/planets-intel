from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShipOrderDraft(Base):
    __tablename__ = "ship_order_drafts"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "linked_account_id",
            "game_id",
            "turn",
            "ship_id",
            name="uq_ship_order_draft_identity",
        ),
        CheckConstraint(
            "movement_mode IN ('waypoint', 'intercept')",
            name="ck_ship_order_drafts_movement_mode",
        ),
        Index(
            "ix_ship_order_drafts_game_turn_account",
            "game_id",
            "turn",
            "linked_account_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    linked_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("planets_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    ship_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Snapshot provenance. Draft values are never canonical observations.
    base_batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("private_observation_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    warp: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    waypoint_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    waypoint_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movement_mode: Mapped[str] = mapped_column(
        String(16),
        server_default="waypoint",
        nullable=False,
    )
    intercept_target_ship_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # Semantic local orders. Mission is intentionally stored by stable display
    # name rather than guessed Nu numeric id until write-back mapping is
    # verified endpoint-by-endpoint.
    friendly_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    mission: Mapped[str | None] = mapped_column(String(80), nullable=True)
    primary_enemy_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
