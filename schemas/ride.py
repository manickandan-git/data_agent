from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RideCreate(BaseModel):
    rider_id: int
    driver_id: int
    requested_at: datetime | None = None
    pickup_time: datetime | None = None
    dropoff_time: datetime | None = None
    pickup_latitude: Decimal | None = None
    pickup_longitude: Decimal | None = None
    dropoff_latitude: Decimal | None = None
    dropoff_longitude: Decimal | None = None
    distance_km: Decimal | None = None
    fare: Decimal | None = None
    surge_multiplier: Decimal | None = None
    status: str | None = None
    cancellation_reason: str | None = None


class RideRead(BaseModel):
    ride_id: int
    rider_id: int
    driver_id: int
    requested_at: datetime | None
    pickup_time: datetime | None
    dropoff_time: datetime | None
    pickup_latitude: Decimal | None
    pickup_longitude: Decimal | None
    dropoff_latitude: Decimal | None
    dropoff_longitude: Decimal | None
    distance_km: Decimal | None
    fare: Decimal | None
    surge_multiplier: Decimal | None
    status: str | None
    cancellation_reason: str | None

    model_config = {"from_attributes": True}
