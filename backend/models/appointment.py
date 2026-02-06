"""Appointment model definitions."""

from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from backend.database import Base


class Appointment(Base):
    """Represents a scheduled appointment."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(String)
