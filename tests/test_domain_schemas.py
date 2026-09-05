from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from data_agent.schemas import (
    PaymentCreate,
    PaymentRead,
    RatingCreate,
    RatingRead,
    RideCreate,
    RideRead,
    UserCreate,
    UserRead,
    VehicleCreate,
    VehicleRead,
)


@pytest.mark.parametrize(
    ("schema", "values"),
    [
        (PaymentCreate, {"ride_id": 1, "user_id": 2}),
        (RatingCreate, {"ride_id": 1, "rider_id": 2, "driver_id": 3, "rating": 5}),
        (RideCreate, {"rider_id": 1, "driver_id": 2}),
        (
            UserCreate,
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "user_type": "rider",
            },
        ),
        (VehicleCreate, {"driver_id": 2}),
    ],
)
def test_create_schemas_accept_minimal_valid_data(schema, values):
    assert schema(**values)


def test_user_and_rating_validation_reject_invalid_values():
    with pytest.raises(ValidationError):
        UserCreate(
            first_name="Ada",
            last_name="Lovelace",
            email="not-an-email",
            user_type="rider",
        )
    with pytest.raises(ValidationError):
        RatingCreate(ride_id=1, rider_id=2, driver_id=3, rating=6)


@pytest.mark.parametrize(
    ("schema", "values"),
    [
        (
            PaymentRead,
            {
                "payment_id": 1,
                "ride_id": 2,
                "user_id": 3,
                "amount": None,
                "payment_method": None,
                "payment_status": None,
                "transaction_id": None,
                "payment_time": None,
            },
        ),
        (
            RatingRead,
            {
                "rating_id": 1,
                "ride_id": 2,
                "rider_id": 3,
                "driver_id": 4,
                "rating": None,
                "comment": None,
                "rated_at": None,
            },
        ),
        (
            RideRead,
            {
                "ride_id": 1,
                "rider_id": 2,
                "driver_id": 3,
                "requested_at": None,
                "pickup_time": None,
                "dropoff_time": None,
                "pickup_latitude": None,
                "pickup_longitude": None,
                "dropoff_latitude": None,
                "dropoff_longitude": None,
                "distance_km": None,
                "fare": None,
                "surge_multiplier": None,
                "status": None,
                "cancellation_reason": None,
            },
        ),
        (
            UserRead,
            {
                "user_id": 1,
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "phone": None,
                "city": None,
                "province": None,
                "user_type": "rider",
                "signup_date": None,
                "is_active": True,
            },
        ),
        (
            VehicleRead,
            {
                "vehicle_id": 1,
                "driver_id": 2,
                "make": None,
                "model": None,
                "year": None,
                "license_plate": None,
                "color": None,
                "is_active": True,
            },
        ),
    ],
)
def test_read_schemas_support_orm_attributes(schema, values):
    result = schema.model_validate(SimpleNamespace(**values))
    assert result.model_dump() == values
