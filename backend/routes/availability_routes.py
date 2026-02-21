from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import SessionLocal, ensure_availability_schema, ensure_appointment_schema
from backend.models.availability import Availability
from backend.models.appointment import Appointment

router = APIRouter(tags=['availability'])

OPEN_TIME = time(9, 0)
LAST_START_TIME = time(15, 45)
DEFAULT_SLOT_DURATION_MINUTES = 15
SLOT_INCREMENT_MINUTES = 15
SLOT_RANGE_DAYS = 28
BOOKING_RANGE_DAYS = 14
BLOCKED_APPOINTMENT_TYPE = 'blocked'
LUNCH_BREAK_START_HOUR = 12
LUNCH_BREAK_END_HOUR = 13
DAY_END_TIME = time(16, 0)
MAX_APPOINTMENT_NOTES_LENGTH = 600
APPOINTMENT_DURATIONS = {
    'immunization': 15,
    'testing': 30,
    'counseling': 60,
    'other': 60,
    'prescription': 15,
}


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


class CalendarSlotResponse(BaseModel):
    date: date
    time: time
    duration_minutes: int
    appointment_type: str
    start_time: datetime
    end_time: datetime
    status: str
    is_available: bool
    is_blocked: bool
    is_booked: bool


class AppointmentTypeOptionResponse(BaseModel):
    appointment_type: str
    duration_minutes: int


class CreateAppointmentRequest(BaseModel):
    student_email: str
    appointment_type: str
    start_time: datetime
    notes: str | None = None

    @field_validator('student_email')
    @classmethod
    def validate_student_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError('Student email is required.')
        if normalized.endswith('@admin.edu'):
            raise ValueError('Only students can schedule appointments.')
        return normalized

    @field_validator('appointment_type')
    @classmethod
    def validate_appointment_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in APPOINTMENT_DURATIONS:
            raise ValueError('Invalid appointment type.')
        return normalized

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        if len(normalized) > MAX_APPOINTMENT_NOTES_LENGTH:
            raise ValueError(f'Notes must be {MAX_APPOINTMENT_NOTES_LENGTH} characters or fewer.')

        return normalized


class AppointmentResponse(BaseModel):
    id: int
    student_email: str
    appointment_type: str
    duration_minutes: int
    start_time: datetime
    end_time: datetime
    status: str
    notes: str | None = None

    class Config:
        from_attributes = True


def ensure_database_ready() -> None:
    try:
        ensure_availability_schema()
        ensure_appointment_schema()
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


def is_lunch_break_slot(slot_time: time) -> bool:
    return LUNCH_BREAK_START_HOUR <= slot_time.hour < LUNCH_BREAK_END_HOUR


def iterate_slot_starts(start_time: datetime, end_time: datetime) -> set[datetime]:
    slots: set[datetime] = set()
    current = start_time.replace(second=0, microsecond=0)

    if current.minute % SLOT_INCREMENT_MINUTES != 0:
        current += timedelta(minutes=SLOT_INCREMENT_MINUTES - (current.minute % SLOT_INCREMENT_MINUTES))

    while current < end_time:
        slots.add(current)
        current += timedelta(minutes=SLOT_INCREMENT_MINUTES)

    return slots


def is_appointment_type_supported(appointment_type: str) -> bool:
    return appointment_type in APPOINTMENT_DURATIONS


def get_appointment_duration_minutes(appointment: Appointment) -> int:
    appointment_type = (appointment.appointment_type or '').strip().lower()
    if appointment_type in APPOINTMENT_DURATIONS:
        return APPOINTMENT_DURATIONS[appointment_type]

    if appointment.start_time and appointment.end_time:
        delta = appointment.end_time - appointment.start_time
        return max(SLOT_INCREMENT_MINUTES, int(delta.total_seconds() // 60))

    return SLOT_INCREMENT_MINUTES


def get_booked_slot_starts(now: datetime, range_end: datetime, db: Session) -> set[datetime]:
    booked_availability_slots = db.query(Availability.start_time, Availability.end_time).filter(
        Availability.is_booked.is_(True),
        Availability.start_time < range_end,
        Availability.end_time > now,
    ).all()

    appointments = db.query(Appointment.start_time, Appointment.end_time).filter(
        Appointment.end_time > now,
        Appointment.start_time < range_end,
    ).all()

    booked_start_times: set[datetime] = set()
    for booked_start, booked_end in booked_availability_slots:
        booked_start_times.update(iterate_slot_starts(booked_start, booked_end))
    for appointment_start, appointment_end in appointments:
        booked_start_times.update(iterate_slot_starts(appointment_start, appointment_end))

    return booked_start_times


def get_blocked_slot_starts(now: datetime, range_end: datetime, db: Session) -> set[datetime]:
    blocked_slots = db.query(Availability.start_time, Availability.end_time).filter(
        Availability.appointment_type == BLOCKED_APPOINTMENT_TYPE,
        Availability.start_time < range_end,
        Availability.end_time > now,
    ).all()
    blocked_start_times: set[datetime] = set()
    for blocked_start, blocked_end in blocked_slots:
        blocked_start_times.update(iterate_slot_starts(blocked_start, blocked_end))

    return {blocked_start.replace(second=0, microsecond=0) for blocked_start in blocked_start_times}


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

    if is_lunch_break_slot(slot_time):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='12:00 PM to 1:00 PM is reserved for lunch and is always blocked.',
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

        overlapping_appointment = db.query(Appointment).filter(
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        ).first()
        if overlapping_appointment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='This time is already booked by a student appointment.',
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

        blocked_start_times = get_blocked_slot_starts(now, range_end, db)
        booked_start_times = get_booked_slot_starts(now, range_end, db)

        generated_slots: list[AvailabilitySlotResponse] = []
        current_day = date.today()
        generated_id = -1

        while current_day <= range_end.date():
            if current_day.weekday() < 5:
                current_start = datetime.combine(current_day, OPEN_TIME)
                last_start = datetime.combine(current_day, LAST_START_TIME)

                while current_start <= last_start:
                    normalized_start = current_start.replace(second=0, microsecond=0)
                    if (
                        current_start > now
                        and normalized_start not in blocked_start_times
                        and normalized_start not in booked_start_times
                        and not is_lunch_break_slot(current_start.time())
                    ):
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


@router.get('/appointment-types', response_model=list[AppointmentTypeOptionResponse])
def list_appointment_types():
    return [
        AppointmentTypeOptionResponse(appointment_type=appointment_type, duration_minutes=duration_minutes)
        for appointment_type, duration_minutes in APPOINTMENT_DURATIONS.items()
    ]


@router.get('/calendar', response_model=list[CalendarSlotResponse])
def list_calendar_slots(
    days: int = Query(default=14, ge=1, le=14),
    appointment_type: str = Query(...),
    db: Session = Depends(get_db),
):
    ensure_database_ready()

    try:
        normalized_appointment_type = appointment_type.strip().lower()
        if not is_appointment_type_supported(normalized_appointment_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid appointment type.',
            )

        duration_minutes = APPOINTMENT_DURATIONS[normalized_appointment_type]
        now = datetime.now()
        range_end = now + timedelta(days=days)
        blocked_start_times = get_blocked_slot_starts(now, range_end, db)
        booked_start_times = get_booked_slot_starts(now, range_end, db)

        calendar_slots: list[CalendarSlotResponse] = []
        current_day = date.today()

        while current_day <= range_end.date():
            if current_day.weekday() < 5:
                current_start = datetime.combine(current_day, OPEN_TIME)
                latest_possible_start = datetime.combine(current_day, DAY_END_TIME) - timedelta(minutes=duration_minutes)

                while current_start <= latest_possible_start:
                    if (
                        current_start > now
                        and current_start < range_end
                    ):
                        slot_end = current_start + timedelta(minutes=duration_minutes)
                        probe = current_start.replace(second=0, microsecond=0)
                        is_valid_start = True

                        while probe < slot_end:
                            if (
                                probe in blocked_start_times
                                or probe in booked_start_times
                                or is_lunch_break_slot(probe.time())
                            ):
                                is_valid_start = False
                                break
                            probe += timedelta(minutes=SLOT_INCREMENT_MINUTES)

                        if is_valid_start:
                            calendar_slots.append(
                                CalendarSlotResponse(
                                    date=current_start.date(),
                                    time=current_start.time(),
                                    duration_minutes=duration_minutes,
                                    appointment_type=normalized_appointment_type,
                                    start_time=current_start,
                                    end_time=slot_end,
                                    status='available',
                                    is_available=True,
                                    is_blocked=False,
                                    is_booked=False,
                                )
                            )

                    current_start += timedelta(minutes=SLOT_INCREMENT_MINUTES)

            current_day += timedelta(days=1)

        return calendar_slots
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.get('/appointments', response_model=list[AppointmentResponse])
def list_appointments(
    admin_email: str = Query(...),
    db: Session = Depends(get_db),
):
    normalized_email = admin_email.strip().lower()
    if not normalized_email.endswith('@admin.edu'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only admins can view booked appointments.',
        )

    ensure_database_ready()

    try:
        appointments = db.query(Appointment).filter(
            Appointment.start_time.is_not(None),
            Appointment.end_time.is_not(None),
            Appointment.end_time > datetime.now(),
        ).order_by(Appointment.start_time.asc()).all()

        return [
            AppointmentResponse(
                id=appointment.id,
                student_email=appointment.student_email or '',
                appointment_type=appointment.appointment_type or 'other',
                duration_minutes=get_appointment_duration_minutes(appointment),
                start_time=appointment.start_time,
                end_time=appointment.end_time,
                status=appointment.status or 'booked',
                notes=appointment.notes,
            )
            for appointment in appointments
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.post('/appointments', response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(data: CreateAppointmentRequest, db: Session = Depends(get_db)):
    ensure_database_ready()

    try:
        duration_minutes = APPOINTMENT_DURATIONS[data.appointment_type]
        start_time = data.start_time.replace(second=0, microsecond=0)
        end_time = start_time + timedelta(minutes=duration_minutes)
        now = datetime.now()
        range_end = now + timedelta(days=BOOKING_RANGE_DAYS)

        if start_time <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Appointments must be scheduled in the future.',
            )

        if start_time.minute % SLOT_INCREMENT_MINUTES != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Appointments must start on 15-minute boundaries.',
            )

        if start_time.date().weekday() >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Appointments can only be scheduled on weekdays.',
            )

        day_open = datetime.combine(start_time.date(), OPEN_TIME)
        day_close = datetime.combine(start_time.date(), DAY_END_TIME)
        if start_time < day_open or end_time > day_close:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Appointment is outside scheduling hours.',
            )

        probe = start_time
        while probe < end_time:
            if is_lunch_break_slot(probe.time()):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Appointments cannot overlap the lunch closure (12:00 PM to 1:00 PM).',
                )
            probe += timedelta(minutes=SLOT_INCREMENT_MINUTES)

        if start_time >= range_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Appointments can only be booked within the next 2 weeks.',
            )

        blocked_overlap = db.query(Availability).filter(
            Availability.appointment_type == BLOCKED_APPOINTMENT_TYPE,
            Availability.start_time < end_time,
            Availability.end_time > start_time,
        ).first()
        if blocked_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='This time is blocked.',
            )

        existing_appointment = db.query(Appointment).filter(
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        ).first()
        if existing_appointment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='This time is already booked.',
            )

        appointment = Appointment(
            student_email=data.student_email,
            appointment_type=data.appointment_type,
            notes=data.notes,
            start_time=start_time,
            end_time=end_time,
            status='booked',
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        return AppointmentResponse(
            id=appointment.id,
            student_email=appointment.student_email or data.student_email,
            appointment_type=appointment.appointment_type or data.appointment_type,
            duration_minutes=duration_minutes,
            start_time=appointment.start_time,
            end_time=appointment.end_time,
            status=appointment.status or 'booked',
            notes=appointment.notes,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc
