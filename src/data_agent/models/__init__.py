# models/__init__.py

# 1. Import the shared declarative base
from data_agent.models.base import Base
from data_agent.models.payment import Payment
from data_agent.models.rating import Rating
from data_agent.models.ride import Ride

# 2. Import every individual table model to register them with metadata
from data_agent.models.user import User
from data_agent.models.vehicle import Vehicle

# 3. Expose them explicitly for clean external imports
__all__ = ["Base", "Payment", "Rating", "Ride", "User", "Vehicle"]
