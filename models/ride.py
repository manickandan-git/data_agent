from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.payment import Payment
    from models.rating import Rating
    from models.user import User


class Ride(Base):
    __tablename__ = "rides"
    __table_args__ = (
        Index("idx_rides_rider_id", "rider_id"),
        Index("idx_rides_driver_id", "driver_id"),
        Index("idx_rides_requested_at", "requested_at"),
        Index("idx_rides_status", "status"),
        {"schema": "public"},
    )

    ride_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rider_id: Mapped[int] = mapped_column(ForeignKey("public.users.user_id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("public.users.user_id"), nullable=False)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pickup_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dropoff_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # DECIMAL mappings map to Python's Decimal type
    pickup_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    pickup_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    dropoff_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    dropoff_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fare: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    surge_multiplier: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)

    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    rider: Mapped["User"] = relationship(foreign_keys=[rider_id], back_populates="rides_as_rider")
    driver: Mapped["User"] = relationship(
        foreign_keys=[driver_id], back_populates="rides_as_driver"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="ride")
    ratings: Mapped[list["Rating"]] = relationship(back_populates="ride")

    def __repr__(self) -> str:
        return f"<Ride ride_id={self.ride_id} status='{self.status}'>"
