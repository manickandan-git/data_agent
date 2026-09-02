# models/__init__.py

# 1. Import the shared declarative base
from models.base import Base
from models.payment import Payment
from models.rating import Rating
from models.ride import Ride

# 2. Import every individual table model to register them with metadata
from models.user import User
from models.vehicle import Vehicle

# 3. Expose them explicitly for clean external imports
__all__ = ["Base", "Payment", "Rating", "Ride", "User", "Vehicle"]
