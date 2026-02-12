from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.availability import Availability

router = APIRouter(tags=['availability'])

ALLOWED_APPOINTMENT_TYPES = {
    'immunization',
    'testing',
    'counseling',
    'other',
    'prescription',
}



OPEN_TIME = time(9, 0)
LAST_START_TIME = time(15, 45)


class CreateAvailabilitySlotRequest(BaseModel):
    admin_email: str
    date: date
    time: time
    duration_minutes: int
    appointment_type: str

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()

        if not normalized.endswith('@admin.edu'):
            raise ValueError('Only admins can create appointment slots.')

        return normalized

    @field_validator('duration_minutes')
    @classmethod
    def validate_duration_minutes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError('Duration must be greater than 0 minutes.')
        return value

    @field_validator('appointment_type')
    @classmethod
    def validate_appointment_type(cls, value: str) -> str:
        normalized = value.strip().lower()

        if normalized not in ALLOWED_APPOINTMENT_TYPES:
            raise ValueError('Invalid appointment type.')

        return normalized


class AvailabilitySlotResponse(BaseModel):
    id: int
    date: date
    time: time
    duration_minutes: int
    appointment_type: str
    start_time: datetime
    end_time: datetime
    is_booked: bool

    class Config:
        from_attributes = True



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post('/slots', response_model=AvailabilitySlotResponse, status_code=status.HTTP_201_CREATED)
def create_availability_slot(data: CreateAvailabilitySlotRequest, db: Session = Depends(get_db)):
    start_time = datetime.combine(data.date, data.time)
    end_time = start_time + timedelta(minutes=data.duration_minutes)

    if data.date.weekday() >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Slots cannot be created on Saturday or Sunday.',
        )

    if data.time < OPEN_TIME or data.time > LAST_START_TIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Slots can only start between 9:00 AM and 3:45 PM.',
        )

    if start_time <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Slots must be created for a future date and time.',
        )

    overlapping_slot = db.query(Availability).filter(
        Availability.start_time < end_time,
        Availability.end_time > start_time,
    ).first()

    if overlapping_slot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='This appointment slot overlaps with an existing slot.',
        )

    slot = Availability(
        date=data.date,
        time=data.time,
        duration_minutes=data.duration_minutes,
        appointment_type=data.appointment_type,
        start_time=start_time,
        end_time=end_time,
        is_booked=False,
    )

    db.add(slot)
    db.commit()
    db.refresh(slot)

    return slot


@router.get('/slots', response_model=list[AvailabilitySlotResponse])
def list_availability_slots(
    students_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    query = db.query(Availability)

    if students_only:
        query = query.filter(Availability.is_booked.is_(False))

    slots = query.order_by(Availability.start_time.asc()).all()
    return slots
