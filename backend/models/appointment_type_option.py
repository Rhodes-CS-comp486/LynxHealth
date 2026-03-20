from sqlalchemy import Column, Integer, String

from backend.database import Base


class AppointmentTypeOption(Base):
    __tablename__ = 'appointment_type_options'

    id = Column(Integer, primary_key=True, index=True)
    appointment_type = Column(String, unique=True, index=True, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
