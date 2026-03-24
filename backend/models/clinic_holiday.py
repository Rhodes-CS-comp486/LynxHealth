from sqlalchemy import Column, Date, Integer, String

from backend.database import Base


class ClinicHoliday(Base):
    __tablename__ = 'clinic_holidays'

    id = Column(Integer, primary_key=True)
    holiday_date = Column(Date, nullable=False, unique=True)
    name = Column(String, nullable=False)
