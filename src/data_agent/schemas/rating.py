from datetime import datetime

from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    ride_id: int
    rider_id: int
    driver_id: int
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = None
    rated_at: datetime | None = None


class RatingRead(BaseModel):
    rating_id: int
    ride_id: int
    rider_id: int
    driver_id: int
    rating: int | None
    comment: str | None
    rated_at: datetime | None

    model_config = {"from_attributes": True}
