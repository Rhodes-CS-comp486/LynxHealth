from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import SessionLocal, ensure_availability_schema
from backend.models.availability import Availability

router = APIRouter(tags=['availability'])

OPEN_TIME = time(9, 0)
LAST_START_TIME = time(15, 45)
DEFAULT_SLOT_DURATION_MINUTES = 15
SLOT_INCREMENT_MINUTES = 15
SLOT_RANGE_DAYS = 28
BLOCKED_APPOINTMENT_TYPE = 'blocked'


class CreateBlockedTimeRequest(BaseModel):
    admin_email: str
    date: date
    time: time

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()

        if not normalized.endswith('@admin.edu'):
            raise ValueError('Only admins can block appointment times.')

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


class BlockedTimeResponse(BaseModel):
    id: int
    date: date
    time: time
    start_time: datetime
    end_time: datetime

    class Config:
        from_attributes = True


def ensure_database_ready() -> None:
    try:
        ensure_availability_schema()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_slot_datetime(slot_date: date, slot_time: time) -> tuple[datetime, datetime]:
    start_time = datetime.combine(slot_date, slot_time)
    end_time = start_time + timedelta(minutes=DEFAULT_SLOT_DURATION_MINUTES)

    if slot_date.weekday() >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Times can only be blocked on weekdays (Monday through Friday).',
        )

    if slot_time < OPEN_TIME or slot_time > LAST_START_TIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Times can only be blocked between 9:00 AM and 3:45 PM.',
        )

    if slot_time.minute % SLOT_INCREMENT_MINUTES != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Times must be on 15-minute boundaries.',
        )

    return start_time, end_time


@router.post('/slots', response_model=BlockedTimeResponse, status_code=status.HTTP_201_CREATED)
def create_blocked_time(data: CreateBlockedTimeRequest, db: Session = Depends(get_db)):
    start_time, end_time = validate_slot_datetime(data.date, data.time)

    ensure_database_ready()

    try:
        overlapping_block = db.query(Availability).filter(
            Availability.appointment_type == BLOCKED_APPOINTMENT_TYPE,
            Availability.start_time < end_time,
            Availability.end_time > start_time,
        ).first()

        if overlapping_block:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='This time is already blocked.',
            )

        blocked_time = Availability(
            date=data.date,
            time=data.time,
            duration_minutes=DEFAULT_SLOT_DURATION_MINUTES,
            appointment_type=BLOCKED_APPOINTMENT_TYPE,
            start_time=start_time,
            end_time=end_time,
            is_booked=False,
        )

        db.add(blocked_time)
        db.commit()
        db.refresh(blocked_time)

        return blocked_time
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.delete('/slots/{slot_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_blocked_time(
    slot_id: int,
    admin_email: str = Query(...),
    db: Session = Depends(get_db),
):
    normalized_email = admin_email.strip().lower()
    if not normalized_email.endswith('@admin.edu'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only admins can unblock appointment times.',
        )

    ensure_database_ready()

    try:
        blocked_time = db.query(Availability).filter(
            Availability.id == slot_id,
            Availability.appointment_type == BLOCKED_APPOINTMENT_TYPE,
        ).first()

        if not blocked_time:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Blocked time not found.',
            )

        db.delete(blocked_time)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.get('/blocked-times', response_model=list[BlockedTimeResponse])
def list_blocked_times(db: Session = Depends(get_db)):
    ensure_database_ready()

    try:
        blocked_times = db.query(Availability).filter(
            Availability.appointment_type == BLOCKED_APPOINTMENT_TYPE,
            Availability.start_time >= datetime.now(),
        ).order_by(Availability.start_time.asc()).all()

        return blocked_times
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.get('/slots', response_model=list[AvailabilitySlotResponse])
def list_availability_slots(
    students_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    del students_only
    ensure_database_ready()

    try:
        now = datetime.now()
        range_end = now + timedelta(days=SLOT_RANGE_DAYS)

        blocked_slots = db.query(Availability).filter(
            Availability.appointment_type == BLOCKED_APPOINTMENT_TYPE,
            Availability.start_time >= now,
            Availability.start_time < range_end,
        ).all()

        blocked_start_times = {blocked_slot.start_time for blocked_slot in blocked_slots}

        generated_slots: list[AvailabilitySlotResponse] = []
        current_day = date.today()
        generated_id = -1

        while current_day <= range_end.date():
            if current_day.weekday() < 5:
                current_start = datetime.combine(current_day, OPEN_TIME)
                last_start = datetime.combine(current_day, LAST_START_TIME)

                while current_start <= last_start:
                    if current_start > now and current_start not in blocked_start_times:
                        generated_slots.append(
                            AvailabilitySlotResponse(
                                id=generated_id,
                                date=current_start.date(),
                                time=current_start.time(),
                                duration_minutes=DEFAULT_SLOT_DURATION_MINUTES,
                                appointment_type='general',
                                start_time=current_start,
                                end_time=current_start + timedelta(minutes=DEFAULT_SLOT_DURATION_MINUTES),
                                is_booked=False,
                            )
                        )
                        generated_id -= 1

                    current_start += timedelta(minutes=SLOT_INCREMENT_MINUTES)

            current_day += timedelta(days=1)

        return generated_slots
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc
