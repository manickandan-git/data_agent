from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.payment import Payment
    from models.rating import Rating
    from models.ride import Ride
    from models.vehicle import Vehicle


class User(Base):
    __tablename__ = "users"
    # No __table_args__ or schema key needed!

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_type: Mapped[str] = mapped_column(String(20), nullable=False)
    signup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="driver")
    rides_as_rider: Mapped[list["Ride"]] = relationship(
        foreign_keys="Ride.rider_id",
        back_populates="rider",
    )
    rides_as_driver: Mapped[list["Ride"]] = relationship(
        foreign_keys="Ride.driver_id",
        back_populates="driver",
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    ratings_given: Mapped[list["Rating"]] = relationship(
        foreign_keys="Rating.rider_id",
        back_populates="rider",
    )
    ratings_received: Mapped[list["Rating"]] = relationship(
        foreign_keys="Rating.driver_id",
        back_populates="driver",
    )
