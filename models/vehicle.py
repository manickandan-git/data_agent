from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user import User


class Vehicle(Base):
    __tablename__ = "vehicles"

    # Typed as ClassVar tuple to clear linter warnings; schema is inherited
    __table_args__: ClassVar[tuple] = (Index("idx_vehicles_driver_id", "driver_id"),)

    vehicle_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("public.users.user_id"),
        nullable=False,
    )
    make: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_plate: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    driver: Mapped["User"] = relationship(back_populates="vehicles")
