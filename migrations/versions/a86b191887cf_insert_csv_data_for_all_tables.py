"""insert_csv_data_for_all_tables

Revision ID: a86b191887cf
Revises: c8e2638fcf8a
Create Date: 2026-09-01 13:21:25.394300
"""
import os
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
from alembic import op
from sqlalchemy import text

# Revision identifiers, handled automatically by Alembic.
revision = 'a86b191887cf'
down_revision = 'c8e2638fcf8a'
branch_labels = None
depends_on = None


def clean_val(val, target_type=str):
    """Safely sanitize CSV cell inputs into native database types."""
    if pd.isna(val) or str(val).strip().lower() in ["", "nan", "none", "null"]:
        return None

    val_str = str(val).strip()

    if target_type == bool:
        return val_str.lower() in ["true", "1", "yes", "t"]
    elif target_type == date:
        try:
            return pd.to_datetime(val_str).date()
        except (ValueError, TypeError):
            return None
    elif target_type == datetime:
        try:
            return pd.to_datetime(val_str)
        except (ValueError, TypeError):
            return None

    return target_type(val)


def upgrade() -> None:
    bind = op.get_bind()
    csv_dir = "./data"

    print("\n[Start Data Migration] Loading CSV datasets into PostgreSQL...")

    # --- 1. USERS ---
    print(" -> Ingesting users.csv...")
    users_df = pd.read_csv(os.path.join(csv_dir, "users.csv"))
    for _, row in users_df.iterrows():
        params = {
            "user_id": int(row["user_id"]),
            "first_name": clean_val(row["first_name"]),
            "last_name": clean_val(row["last_name"]),
            "email": clean_val(row["email"]),
            "phone": clean_val(row.get("phone")),
            "city": clean_val(row.get("city")),
            "province": clean_val(row.get("province")),
            "user_type": clean_val(row["user_type"]),
            "signup_date": clean_val(row.get("signup_date"), date),
            "is_active": clean_val(row.get("is_active"), bool)
        }
        bind.execute(
            text("""
                INSERT INTO public.users (user_id, first_name, last_name, email, phone, city, province, user_type, signup_date, is_active)
                VALUES (:user_id, :first_name, :last_name, :email, :phone, :city, :province, :user_type, :signup_date, :is_active)
                ON CONFLICT (user_id) DO NOTHING
            """),
            params
        )

    # --- 2. VEHICLES ---
    print(" -> Ingesting vehicles.csv...")
    vehicles_df = pd.read_csv(os.path.join(csv_dir, "vehicles.csv"))
    for _, row in vehicles_df.iterrows():
        params = {
            "vehicle_id": int(row["vehicle_id"]),
            "driver_id": int(row["driver_id"]),
            "make": clean_val(row.get("make")),
            "model": clean_val(row.get("model")),
            "year": clean_val(row.get("year"), int),
            "license_plate": clean_val(row.get("license_plate")),
            "color": clean_val(row.get("color")),
            "is_active": clean_val(row.get("is_active"), bool)
        }
        bind.execute(
            text("""
                INSERT INTO public.vehicles (vehicle_id, driver_id, make, model, year, license_plate, color, is_active)
                VALUES (:vehicle_id, :driver_id, :make, :model, :year, :license_plate, :color, :is_active)
                ON CONFLICT (vehicle_id) DO NOTHING
            """),
            params
        )

    # --- 3. RIDES ---
    print(" -> Ingesting rides.csv...")
    rides_df = pd.read_csv(os.path.join(csv_dir, "rides.csv"))
    for _, row in rides_df.iterrows():
        params = {
            "ride_id": int(row["ride_id"]),
            "rider_id": int(row["rider_id"]),
            "driver_id": int(row["driver_id"]),
            "requested_at": clean_val(row.get("requested_at"), datetime),
            "pickup_time": clean_val(row.get("pickup_time"), datetime),
            "dropoff_time": clean_val(row.get("dropoff_time"), datetime),
            "pickup_latitude": clean_val(row.get("pickup_latitude"), Decimal),
            "pickup_longitude": clean_val(row.get("pickup_longitude"), Decimal),
            "dropoff_latitude": clean_val(row.get("dropoff_latitude"), Decimal),
            "dropoff_longitude": clean_val(row.get("dropoff_longitude"), Decimal),
            "distance_km": clean_val(row.get("distance_km"), Decimal),
            "fare": clean_val(row.get("fare"), Decimal),
            "surge_multiplier": clean_val(row.get("surge_multiplier"), Decimal),
            "status": clean_val(row.get("status")),
            "cancellation_reason": clean_val(row.get("cancellation_reason"))
        }
        bind.execute(
            text("""
                INSERT INTO public.rides (ride_id, rider_id, driver_id, requested_at, pickup_time, dropoff_time, pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude, distance_km, fare, surge_multiplier, status, cancellation_reason)
                VALUES (:ride_id, :rider_id, :driver_id, :requested_at, :pickup_time, :dropoff_time, :pickup_latitude, :pickup_longitude, :dropoff_latitude, :dropoff_longitude, :distance_km, :fare, :surge_multiplier, :status, :cancellation_reason)
                ON CONFLICT (ride_id) DO NOTHING
            """),
            params
        )

    # --- 4. PAYMENTS ---
    print(" -> Ingesting payments.csv...")
    payments_df = pd.read_csv(os.path.join(csv_dir, "payments.csv"))
    for _, row in payments_df.iterrows():
        params = {
            "payment_id": int(row["payment_id"]),
            "ride_id": int(row["ride_id"]),
            "user_id": int(row["user_id"]),
            "amount": clean_val(row.get("amount"), Decimal),
            "payment_method": clean_val(row.get("payment_method")),
            "payment_status": clean_val(row.get("payment_status")),
            "transaction_id": clean_val(row.get("transaction_id")),
            "payment_time": clean_val(row.get("payment_time"), datetime)
        }
        bind.execute(
            text("""
                INSERT INTO public.payments (payment_id, ride_id, user_id, amount, payment_method, payment_status, transaction_id, payment_time)
                VALUES (:payment_id, :ride_id, :user_id, :amount, :payment_method, :payment_status, :transaction_id, :payment_time)
                ON CONFLICT (payment_id) DO NOTHING
            """),
            params
        )

    # --- 5. RATINGS ---
    print(" -> Ingesting ratings.csv...")
    ratings_df = pd.read_csv(os.path.join(csv_dir, "ratings.csv"))
    for _, row in ratings_df.iterrows():
        params = {
            "rating_id": int(row["rating_id"]),
            "ride_id": int(row["ride_id"]),
            "rider_id": int(row["rider_id"]),
            "driver_id": int(row["driver_id"]),
            "rating": clean_val(row.get("rating"), int),
            "comment": clean_val(row.get("comment")),
            "rated_at": clean_val(row.get("rated_at"), datetime)
        }
        bind.execute(
            text("""
                INSERT INTO public.ratings (rating_id, ride_id, rider_id, driver_id, rating, comment, rated_at)
                VALUES (:rating_id, :ride_id, :rider_id, :driver_id, :rating, :comment, :rated_at)
                ON CONFLICT (rating_id) DO NOTHING
            """),
            params
        )

    print("[Success Data Migration] All CSV datasets synced directly with PostgreSQL.")


def downgrade() -> None:
    op.execute(text("TRUNCATE TABLE public.ratings, public.payments, public.rides, public.vehicles, public.users CASCADE"))

