from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PublicPlayerHistoryCache(Base):
    """Transport cache for one public Planets.nu player-history query.

    This table is not a behavioral or relationship model. It only stores the
    latest public API response plus fetch provenance so derived commander
    summaries can be rebuilt without browser-side fan-out.
    """

    __tablename__ = "public_player_history_cache"

    __table_args__ = (
        Index(
            "ix_public_player_history_cache_fetched_at",
            "fetched_at",
        ),
    )

    username_normalized: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    status_filter: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    payload: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
