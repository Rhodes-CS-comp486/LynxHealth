"""
SQLAlchemy model for appointment type options in the LynxHealth system.
"""
from sqlalchemy import Column, Integer, String

from backend.database import Base


class AppointmentTypeOption(Base):
    """Represents a type of appointment and its default duration."""
    __tablename__ = 'appointment_type_options'

    id = Column(Integer, primary_key=True, index=True)
    appointment_type = Column(String, unique=True, index=True, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
