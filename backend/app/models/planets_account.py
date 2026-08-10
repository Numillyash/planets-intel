from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlanetsAccount(Base):
    __tablename__ = "planets_accounts"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "planets_username_normalized",
            name="uq_planets_account_user_username",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "app_users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    planets_username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    planets_username_normalized: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    planets_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    api_key_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
