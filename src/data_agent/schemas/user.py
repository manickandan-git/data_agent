from datetime import date

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    city: str | None = None
    province: str | None = None
    user_type: str
    signup_date: date | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None
    city: str | None
    province: str | None
    user_type: str
    signup_date: date | None
    is_active: bool | None

    model_config = {"from_attributes": True}
