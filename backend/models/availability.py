from sqlalchemy import Column, Integer, Date, Time, DateTime, Boolean, String
from backend.database import Base


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True)
    date = Column(Date)
    time = Column(Time)
    duration_minutes = Column(Integer)
    appointment_type = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    is_booked = Column(Boolean, default=False)
