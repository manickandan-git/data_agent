from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    ride_id: int
    user_id: int
    amount: Decimal | None = None
    payment_method: str | None = None
    payment_status: str | None = None
    transaction_id: str | None = None
    payment_time: datetime | None = None


class PaymentRead(BaseModel):
    payment_id: int
    ride_id: int
    user_id: int
    amount: Decimal | None
    payment_method: str | None
    payment_status: str | None
    transaction_id: str | None
    payment_time: datetime | None

    model_config = {"from_attributes": True}
