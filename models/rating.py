from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.ride import Ride
    from models.user import User


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="chk_rating"),
        Index("idx_ratings_ride_id", "ride_id"),
        Index("idx_ratings_driver_id", "driver_id"),
        {"schema": "public"},
    )

    rating_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ride_id: Mapped[int] = mapped_column(ForeignKey("public.rides.ride_id"), nullable=False)
    rider_id: Mapped[int] = mapped_column(ForeignKey("public.users.user_id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("public.users.user_id"), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    rated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    ride: Mapped["Ride"] = relationship(back_populates="ratings")
    rider: Mapped["User"] = relationship(foreign_keys=[rider_id], back_populates="ratings_given")
    driver: Mapped["User"] = relationship(
        foreign_keys=[driver_id], back_populates="ratings_received"
    )

    def __repr__(self) -> str:
        return f"<Rating rating_id={self.rating_id} score={self.rating}>"
