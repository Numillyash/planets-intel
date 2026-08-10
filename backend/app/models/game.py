from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status_id: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    status_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    current_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    slots: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    is_custom: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
