from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_agent.models.base import Base

if TYPE_CHECKING:
    from data_agent.models.ride import Ride
    from data_agent.models.user import User


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("idx_payments_ride_id", "ride_id"),
        Index("idx_payments_user_id", "user_id"),
        {"schema": "public"},
    )

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ride_id: Mapped[int] = mapped_column(ForeignKey("public.rides.ride_id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("public.users.user_id"), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    payment_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    ride: Mapped["Ride"] = relationship(back_populates="payments")
    user: Mapped["User"] = relationship(back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment payment_id={self.payment_id} amount={self.amount}>"
