from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DashboardIntelShare(Base):
    __tablename__ = "dashboard_intel_shares"

    __table_args__ = (
        CheckConstraint(
            "account_low_id < account_high_id",
            name="ck_dashboard_intel_share_account_order",
        ),
        UniqueConstraint(
            "account_low_id",
            "account_high_id",
            name="uq_dashboard_intel_share_pair",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    account_low_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "planets_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    account_high_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "planets_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    requested_by_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "planets_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    approved_low_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    approved_high_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
