"""Availability model definitions."""

from sqlalchemy import Column, Integer, DateTime, Boolean
from backend.database import Base


class Availability(Base):
    """Represents available appointment slots."""
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    is_booked = Column(Boolean, default=False)
