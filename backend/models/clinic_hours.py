"""
SQLAlchemy model for clinic operating hours in the LynxHealth system.
"""
from sqlalchemy import Boolean, Column, Integer, Time

from backend.database import Base


class ClinicHours(Base):
    """Represents the open/close hours for a day of the week."""
    __tablename__ = 'clinic_hours'

    id = Column(Integer, primary_key=True)
    day_of_week = Column(Integer, nullable=False, unique=True)
    is_open = Column(Boolean, nullable=False, default=False)
    open_time = Column(Time, nullable=True)
    close_time = Column(Time, nullable=True)
