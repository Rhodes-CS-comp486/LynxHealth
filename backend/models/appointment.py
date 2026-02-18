from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from backend.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    student_email = Column(String)
    appointment_type = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(String)
