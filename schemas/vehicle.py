from pydantic import BaseModel


class VehicleCreate(BaseModel):
    driver_id: int
    make: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    color: str | None = None
    is_active: bool | None = None


class VehicleRead(BaseModel):
    vehicle_id: int
    driver_id: int
    make: str | None
    model: str | None
    year: int | None
    license_plate: str | None
    color: str | None
    is_active: bool | None

    model_config = {"from_attributes": True}
