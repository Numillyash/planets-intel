from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PublicGameInfoCache(Base):
    """Transport cache for public /game/loadinfo payloads.

    The payload remains a public factual source. Participation intervals and
    pairwise overlap summaries are derived from it at read time and are not
    written back into this table.
    """

    __tablename__ = "public_game_info_cache"

    __table_args__ = (
        Index(
            "ix_public_game_info_cache_fetched_at",
            "fetched_at",
        ),
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
