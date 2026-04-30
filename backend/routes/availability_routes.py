"""
Availability, appointment, and clinic-hours endpoints for the LynxHealth API.

This module owns the bulk of the scheduling domain:

* Clinic hours and holiday overrides (admin configures, everyone reads)
* Admin-managed appointment types and their durations
* Admin "blocked times" that remove specific 15-minute slots from availability
* Student-facing slot generation and appointment booking / rescheduling /
  cancellation flows, including ICS calendar export

Validation helpers at the top of the file enforce the business rules shared by
every endpoint (clinic operating days, 15-minute boundaries, lunch closure,
two-week booking horizon, etc.).
"""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import (
    ensure_availability_schema,
    ensure_clinic_holidays_schema,
    ensure_clinic_hours_schema,
    ensure_appointment_schema,
    ensure_appointment_type_option_schema,
)
from backend.dependencies import get_db
from backend.models.availability import Availability
from backend.models.clinic_holiday import ClinicHoliday
from backend.models.clinic_hours import ClinicHours
from backend.models.appointment import Appointment
from backend.models.appointment_type_option import AppointmentTypeOption

router = APIRouter(tags=['availability'])

OPEN_TIME = time(9, 0)
DEFAULT_SLOT_DURATION_MINUTES = 15
SLOT_INCREMENT_MINUTES = 15
APPOINTMENT_DURATION_INCREMENT_MINUTES = 5
SLOT_RANGE_DAYS = 28
BOOKING_RANGE_DAYS = 14
BLOCKED_APPOINTMENT_TYPE = 'blocked'
LUNCH_BREAK_START_HOUR = 12
LUNCH_BREAK_END_HOUR = 13
DAY_END_TIME = time(16, 0)
MAX_APPOINTMENT_NOTES_LENGTH = 600
MIN_APPOINTMENT_DURATION_MINUTES = 5
MAX_APPOINTMENT_DURATION_MINUTES = 240
MAX_HOLIDAY_NAME_LENGTH = 80
DAY_NAMES = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')


def format_invalid_appointment_type_characters(invalid_characters: list[str]) -> str:
    """Build a user-facing error message listing disallowed characters in a type name."""
    if len(invalid_characters) == 1:
        return f"Please use only letters, numbers, spaces, or hyphens in the type name. Remove '{invalid_characters[0]}'."

    formatted = ', '.join(f"'{character}'" for character in invalid_characters[:-1])
    formatted += f" or '{invalid_characters[-1]}'"
    return f'Please use only letters, numbers, spaces, or hyphens in the type name. Remove {formatted}.'


def normalize_appointment_type_name(value: str) -> str:
    """Validate and slugify an appointment type name (lowercase, underscores).

    Raises ``ValueError`` if the name is empty, contains disallowed characters,
    is longer than 50 characters, or collides with the reserved ``'blocked'``
    sentinel used for admin-blocked availability slots.
    """
    normalized = ' '.join(value.strip().lower().split())

    if not normalized:
        raise ValueError('Enter a name for the appointment type.')

    invalid_characters: list[str] = []
    for character in normalized:
        if character.isalnum() or character in {' ', '-'}:
            continue
        if character not in invalid_characters:
            invalid_characters.append(character)

    if invalid_characters:
        raise ValueError(format_invalid_appointment_type_characters(invalid_characters))

    slug = normalized.replace(' ', '_')

    if len(slug) > 50:
        raise ValueError('Keep the type name to 50 characters or fewer.')
    if slug == BLOCKED_APPOINTMENT_TYPE:
        raise ValueError('That name is reserved. Please choose a different appointment type.')

    return slug


def normalize_stored_appointment_type_name(value: str | None) -> str | None:
    """Best-effort normalization for appointment types already sitting in the database.

    Unlike :func:`normalize_appointment_type_name` this never raises: legacy rows
    that wouldn't pass the strict validator fall back to a lowercase compacted
    form so lookups still work without rejecting existing data.
    """
    if value is None:
        return None

    normalized = ' '.join(value.strip().split())
    if not normalized:
        return None

    try:
        return normalize_appointment_type_name(normalized)
    except ValueError:
        return normalized.lower()


def normalize_appointment_type_lookup_name(value: str) -> str:
    try:
        return normalize_appointment_type_name(value)
    except ValueError:
        try:
            return normalize_appointment_type_name(value.replace('_', ' '))
        except ValueError:
            return ' '.join(value.strip().lower().split())


def get_appointment_type_lookup_keys(value: str | None) -> set[str]:
    """Produce every plausible spelling of an appointment type for loose matching.

    Used when looking up stored rows by a user-provided name — tolerates
    mixed case, underscores vs. hyphens vs. spaces, and whitespace.
    """
    if value is None:
        return set()

    compacted = ' '.join(value.strip().split())
    if not compacted:
        return set()

    lower_value = compacted.lower()
    keys = {
        lower_value,
        lower_value.replace('_', ' '),
        lower_value.replace('-', ' '),
        lower_value.replace('_', '-'),
        lower_value.replace('-', '_'),
    }

    normalized = normalize_stored_appointment_type_name(compacted)
    if normalized:
        keys.add(normalized)
        keys.add(normalized.replace('_', ' '))
        keys.add(normalized.replace('-', ' '))

    keys.add(''.join(character for character in lower_value if character.isalnum()))
    return {key for key in keys if key}


def normalize_appointment_notes(value: str | None) -> str | None:
    """Trim appointment notes and enforce the ``MAX_APPOINTMENT_NOTES_LENGTH`` cap.

    Returns ``None`` when the trimmed value is empty. Raises ``ValueError``
    if the text exceeds the maximum allowed length.
    """
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if len(normalized) > MAX_APPOINTMENT_NOTES_LENGTH:
        raise ValueError(f'Notes must be {MAX_APPOINTMENT_NOTES_LENGTH} characters or fewer.')

    return normalized


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


class DailyHoursSettingRequest(BaseModel):
    day_of_week: int
    is_open: bool
    open_time: time | None = None
    close_time: time | None = None

    @field_validator('day_of_week')
    @classmethod
    def validate_day_of_week(cls, value: int) -> int:
        if value < 0 or value > 6:
            raise ValueError('day_of_week must be between 0 (Monday) and 6 (Sunday).')
        return value

    @field_validator('close_time')
    @classmethod
    def validate_open_close_times(cls, value: time | None, info):
        is_open = info.data.get('is_open')
        open_time_value = info.data.get('open_time')

        if is_open:
            if open_time_value is None or value is None:
                raise ValueError('Open days require both open_time and close_time.')
            if value <= open_time_value:
                raise ValueError('close_time must be after open_time.')
        return value


class HolidaySettingRequest(BaseModel):
    holiday_date: date
    name: str
    is_annual: bool = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('Holiday name is required.')
        if len(normalized) > MAX_HOLIDAY_NAME_LENGTH:
            raise ValueError(f'Holiday name must be {MAX_HOLIDAY_NAME_LENGTH} characters or fewer.')
        return normalized


class UpdateClinicHoursRequest(BaseModel):
    admin_email: str
    daily_hours: list[DailyHoursSettingRequest]
    holidays: list[HolidaySettingRequest] = []

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.endswith('@admin.edu'):
            raise ValueError('Only admins can update clinic hours.')
        return normalized

    @field_validator('daily_hours')
    @classmethod
    def validate_daily_hours(cls, value: list[DailyHoursSettingRequest]) -> list[DailyHoursSettingRequest]:
        if len(value) != 7:
            raise ValueError('daily_hours must include all 7 days of the week.')
        day_indexes = {entry.day_of_week for entry in value}
        if day_indexes != set(range(7)):
            raise ValueError('daily_hours must include each day_of_week exactly once.')
        return value

    @field_validator('holidays')
    @classmethod
    def validate_holidays(cls, value: list[HolidaySettingRequest]) -> list[HolidaySettingRequest]:
        if len({holiday.holiday_date for holiday in value}) != len(value):
            raise ValueError('Holiday dates must be unique.')
        return value


class DailyHoursSettingResponse(BaseModel):
    day_of_week: int
    day_name: str
    is_open: bool
    open_time: time | None = None
    close_time: time | None = None


class HolidaySettingResponse(BaseModel):
    id: int | None = None
    holiday_date: date
    name: str
    is_annual: bool = False

    model_config = ConfigDict(from_attributes=True)


class ClinicHoursResponse(BaseModel):
    daily_hours: list[DailyHoursSettingResponse]
    holidays: list[HolidaySettingResponse]


class AvailabilitySlotResponse(BaseModel):
    id: int
    date: date
    time: time
    duration_minutes: int
    appointment_type: str
    start_time: datetime
    end_time: datetime
    is_booked: bool

    model_config = ConfigDict(from_attributes=True)


class BlockedTimeResponse(BaseModel):
    id: int
    date: date
    time: time
    start_time: datetime
    end_time: datetime

    model_config = ConfigDict(from_attributes=True)


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
    id: int | None = None
    appointment_type: str
    duration_minutes: int


class CreateAppointmentTypeRequest(BaseModel):
    admin_email: str
    appointment_type: str
    duration_minutes: int

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()

        if not normalized.endswith('@admin.edu'):
            raise ValueError('Only admins can create appointment types.')

        return normalized

    @field_validator('appointment_type')
    @classmethod
    def validate_appointment_type(cls, value: str) -> str:
        return normalize_appointment_type_name(value)

    @field_validator('duration_minutes')
    @classmethod
    def validate_duration_minutes(cls, value: int) -> int:
        if value < MIN_APPOINTMENT_DURATION_MINUTES or value > MAX_APPOINTMENT_DURATION_MINUTES:
            raise ValueError('Duration must be between 5 and 240 minutes.')
        if value % APPOINTMENT_DURATION_INCREMENT_MINUTES != 0:
            raise ValueError('Duration must be in 5-minute increments.')
        return value


class DeleteAppointmentTypeRequest(BaseModel):
    admin_email: str
    appointment_type: str | None = None
    appointment_type_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices('appointment_type_id', 'appointmentTypeId', 'appointmentTypeID', 'id'),
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()

        if not normalized.endswith('@admin.edu'):
            raise ValueError('Only admins can delete appointment types.')

        return normalized

    @field_validator('appointment_type')
    @classmethod
    def validate_appointment_type(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @model_validator(mode='after')
    def require_delete_target(self):
        if self.appointment_type_id is None and not self.appointment_type:
            raise ValueError('Choose an appointment type to delete.')
        return self


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
        if not normalized:
            raise ValueError('Appointment type is required.')
        return normalized

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_appointment_notes(value)


class AppointmentResponse(BaseModel):
    id: int
    student_email: str
    appointment_type: str
    duration_minutes: int
    start_time: datetime
    end_time: datetime
    status: str
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DeleteAppointmentTypeResponse(BaseModel):
    deleted_type: AppointmentTypeOptionResponse
    upcoming_appointments: list[AppointmentResponse]


class UpdateAppointmentNotesRequest(BaseModel):
    student_email: str
    notes: str | None = None

    @field_validator('student_email')
    @classmethod
    def validate_student_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError('Student email is required.')
        if normalized.endswith('@admin.edu'):
            raise ValueError('Only students can update appointment notes.')
        return normalized

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_appointment_notes(value)


class RescheduleAppointmentRequest(BaseModel):
    student_email: str
    start_time: datetime

    @field_validator('student_email')
    @classmethod
    def validate_student_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError('Student email is required.')
        if normalized.endswith('@admin.edu'):
            raise ValueError('Only students can reschedule appointments.')
        return normalized


def to_appointment_response(appointment: Appointment, duration_map: dict[str, int] | None = None) -> AppointmentResponse:
    return AppointmentResponse(
        id=appointment.id,
        student_email=appointment.student_email or '',
        appointment_type=appointment.appointment_type or 'other',
        duration_minutes=get_appointment_duration_minutes(appointment, duration_map),
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        status=appointment.status or 'booked',
        notes=appointment.notes,
    )


def format_ics_datetime(value: datetime) -> str:
    return value.strftime('%Y%m%dT%H%M%S')


def escape_ics_text(value: str) -> str:
    return (
        value
        .replace('\\', '\\\\')
        .replace(';', r'\;')
        .replace(',', r'\,')
        .replace('\r\n', r'\n')
        .replace('\n', r'\n')
    )


def create_appointment_ics(appointment: Appointment, summary: str) -> str:
    start_time = appointment.start_time
    end_time = appointment.end_time
    if start_time is None or end_time is None:
        raise ValueError('Appointment is missing date or time values.')

    notes = appointment.notes or 'No notes provided.'
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Lynx Health//Appointments//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:appointment-{appointment.id}@lynxhealth.local',
        f'DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
        f'DTSTART:{format_ics_datetime(start_time)}',
        f'DTEND:{format_ics_datetime(end_time)}',
        f'SUMMARY:{escape_ics_text(summary)}',
        f'DESCRIPTION:{escape_ics_text(notes)}',
        'LOCATION:Lynx Health Center',
        'STATUS:CONFIRMED',
        'END:VEVENT',
        'END:VCALENDAR',
        '',
    ]
    return '\r\n'.join(lines)


def format_calendar_summary_from_type(appointment_type: str | None) -> str:
    normalized = (appointment_type or 'appointment').strip().replace('_', ' ')
    if not normalized:
        normalized = 'appointment'
    title_cased = ' '.join(part.capitalize() for part in normalized.split())
    return f'Health Center Appointment: {title_cased}'


def ensure_database_ready() -> None:
    """Run all schema migrations, raising 503 if the database is unreachable.

    Call this at the top of every endpoint that touches the database so the
    client gets a clean error when Postgres is misconfigured instead of a
    generic 500.
    """
    try:
        ensure_availability_schema()
        ensure_appointment_schema()
        ensure_appointment_type_option_schema()
        ensure_clinic_hours_schema()
        ensure_clinic_holidays_schema()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


def get_default_daily_hours() -> dict[int, DailyHoursSettingResponse]:
    """Default weekday hours used before an admin saves custom clinic hours.

    Monday–Friday are open 9:00 AM – 4:00 PM; Saturday and Sunday are closed.
    """
    defaults: dict[int, DailyHoursSettingResponse] = {}
    for day_of_week in range(7):
        weekday_open = day_of_week < 5
        defaults[day_of_week] = DailyHoursSettingResponse(
            day_of_week=day_of_week,
            day_name=DAY_NAMES[day_of_week],
            is_open=weekday_open,
            open_time=OPEN_TIME if weekday_open else None,
            close_time=DAY_END_TIME if weekday_open else None,
        )
    return defaults


def get_daily_hours_map(db: Session) -> dict[int, DailyHoursSettingResponse]:
    daily_hours = get_default_daily_hours()
    rows = db.query(ClinicHours).all()

    for row in rows:
        if row.day_of_week is None or row.day_of_week < 0 or row.day_of_week > 6:
            continue
        daily_hours[row.day_of_week] = DailyHoursSettingResponse(
            day_of_week=row.day_of_week,
            day_name=DAY_NAMES[row.day_of_week],
            is_open=bool(row.is_open),
            open_time=row.open_time,
            close_time=row.close_time,
        )

    return daily_hours


def get_holiday_lookup(db: Session) -> dict[date, HolidaySettingResponse]:
    holidays = db.query(ClinicHoliday).order_by(ClinicHoliday.holiday_date.asc()).all()
    return {
        holiday.holiday_date: HolidaySettingResponse(
            id=holiday.id,
            holiday_date=holiday.holiday_date,
            name=holiday.name,
            is_annual=bool(holiday.is_annual),
        )
        for holiday in holidays
        if holiday.holiday_date is not None and holiday.name
    }


def get_annual_holiday_pairs(holiday_lookup: dict[date, HolidaySettingResponse]) -> set[tuple[int, int]]:
    return {
        (holiday_date.month, holiday_date.day)
        for holiday_date, holiday in holiday_lookup.items()
        if holiday.is_annual
    }


def is_clinic_closed_on(
    day: date,
    daily_hours_map: dict[int, DailyHoursSettingResponse],
    holiday_lookup: dict[date, HolidaySettingResponse],
    annual_holidays: set[tuple[int, int]] | None = None,
) -> bool:
    """Return ``True`` when ``day`` is a holiday or falls on a closed weekday.

    ``annual_holidays`` contains ``(month, day)`` pairs that recur every year
    regardless of the original holiday date.
    """
    annual_holidays = annual_holidays or set()
    if day in holiday_lookup:
        return True
    if (day.month, day.day) in annual_holidays:
        return True
    day_hours = daily_hours_map.get(day.weekday())
    if not day_hours:
        return True
    if not day_hours.is_open:
        return True
    return day_hours.open_time is None or day_hours.close_time is None


def get_clinic_day_bounds(
    day: date,
    daily_hours_map: dict[int, DailyHoursSettingResponse],
    holiday_lookup: dict[date, HolidaySettingResponse],
    annual_holidays: set[tuple[int, int]] | None = None,
) -> tuple[datetime, datetime] | None:
    """Return ``(open_datetime, close_datetime)`` for ``day`` or ``None`` if closed."""
    if is_clinic_closed_on(day, daily_hours_map, holiday_lookup, annual_holidays):
        return None
    day_hours = daily_hours_map[day.weekday()]
    return (
        datetime.combine(day, day_hours.open_time),
        datetime.combine(day, day_hours.close_time),
    )


def get_appointment_duration_map(db: Session) -> dict[str, int]:
    options = db.query(AppointmentTypeOption).order_by(
        AppointmentTypeOption.appointment_type.asc()
    ).all()

    return {
        (option.appointment_type or '').strip().lower(): option.duration_minutes
        for option in options
        if option.appointment_type and option.duration_minutes
    }


def is_lunch_break_slot(slot_time: time) -> bool:
    """Return ``True`` if ``slot_time`` falls inside the 12 PM – 1 PM lunch closure."""
    return LUNCH_BREAK_START_HOUR <= slot_time.hour < LUNCH_BREAK_END_HOUR


def iterate_slot_starts(start_time: datetime, end_time: datetime) -> set[datetime]:
    """Return every 15-minute slot start within ``[start_time, end_time)``.

    Used to decompose a multi-slot appointment or blocked range into the
    set of individual 15-minute boundaries it occupies.
    """
    slots: set[datetime] = set()
    current = start_time.replace(second=0, microsecond=0)

    if current.minute % SLOT_INCREMENT_MINUTES != 0:
        current += timedelta(minutes=SLOT_INCREMENT_MINUTES - (current.minute % SLOT_INCREMENT_MINUTES))

    while current < end_time:
        slots.add(current)
        current += timedelta(minutes=SLOT_INCREMENT_MINUTES)

    return slots


def is_appointment_type_supported(appointment_type: str, duration_map: dict[str, int]) -> bool:
    return appointment_type in duration_map


def get_appointment_duration_minutes(appointment: Appointment, duration_map: dict[str, int] | None = None) -> int:
    appointment_type = (appointment.appointment_type or '').strip().lower()
    if duration_map and appointment_type in duration_map:
        return duration_map[appointment_type]

    if appointment.start_time and appointment.end_time:
        delta = appointment.end_time - appointment.start_time
        return max(APPOINTMENT_DURATION_INCREMENT_MINUTES, int(delta.total_seconds() // 60))

    return SLOT_INCREMENT_MINUTES


def validate_appointment_window(
    start_time: datetime,
    duration_minutes: int,
    now: datetime,
    daily_hours_map: dict[int, DailyHoursSettingResponse] | None = None,
    holiday_lookup: dict[date, HolidaySettingResponse] | None = None,
    annual_holidays: set[tuple[int, int]] | None = None,
) -> datetime:
    """Validate a proposed appointment window and return its end datetime.

    Enforces every scheduling rule in one place: must be in the future, must
    start on a 15-minute boundary, clinic must be open on that day, must fit
    fully inside the day's operating hours, must not overlap the lunch
    closure, and must fall within the :data:`BOOKING_RANGE_DAYS` horizon.

    Raises ``HTTPException`` with status 400 for any violation.
    """
    normalized_start = start_time.replace(second=0, microsecond=0)
    end_time = normalized_start + timedelta(minutes=duration_minutes)
    range_end = now + timedelta(days=BOOKING_RANGE_DAYS)
    daily_hours_map = daily_hours_map or get_default_daily_hours()
    holiday_lookup = holiday_lookup or {}
    annual_holidays = annual_holidays or set()

    if normalized_start <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Appointments must be scheduled in the future.',
        )

    if normalized_start.minute % SLOT_INCREMENT_MINUTES != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Appointments must start on 15-minute boundaries.',
        )

    if is_clinic_closed_on(normalized_start.date(), daily_hours_map, holiday_lookup, annual_holidays):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Appointments can only be scheduled on clinic operating days.',
        )

    day_bounds = get_clinic_day_bounds(normalized_start.date(), daily_hours_map, holiday_lookup, annual_holidays)
    if day_bounds is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Appointments can only be scheduled on clinic operating days.',
        )
    day_open, day_close = day_bounds
    if normalized_start < day_open or end_time > day_close:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Appointment is outside scheduling hours.',
        )

    probe = normalized_start
    while probe < end_time:
        if is_lunch_break_slot(probe.time()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Appointments cannot overlap the lunch closure (12:00 PM to 1:00 PM).',
            )
        probe += timedelta(minutes=SLOT_INCREMENT_MINUTES)

    if normalized_start >= range_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Appointments can only be booked within the next 2 weeks.',
        )

    return end_time


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


def validate_slot_datetime(
    slot_date: date,
    slot_time: time,
    daily_hours_map: dict[int, DailyHoursSettingResponse] | None = None,
    holiday_lookup: dict[date, HolidaySettingResponse] | None = None,
    annual_holidays: set[tuple[int, int]] | None = None,
) -> tuple[datetime, datetime]:
    """Validate an admin-blocked 15-minute slot and return ``(start, end)`` datetimes.

    Uses the same open/closed/lunch rules as ``validate_appointment_window``
    but scoped to a single 15-minute slot (``DEFAULT_SLOT_DURATION_MINUTES``).
    """
    daily_hours_map = daily_hours_map or get_default_daily_hours()
    holiday_lookup = holiday_lookup or {}
    annual_holidays = annual_holidays or set()
    start_time = datetime.combine(slot_date, slot_time)
    end_time = start_time + timedelta(minutes=DEFAULT_SLOT_DURATION_MINUTES)

    if is_clinic_closed_on(slot_date, daily_hours_map, holiday_lookup, annual_holidays):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Times can only be blocked on clinic operating days.',
        )

    day_bounds = get_clinic_day_bounds(slot_date, daily_hours_map, holiday_lookup, annual_holidays)
    if day_bounds is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Times can only be blocked on clinic operating days.',
        )
    day_open, day_close = day_bounds
    latest_start = day_close - timedelta(minutes=DEFAULT_SLOT_DURATION_MINUTES)

    if slot_time < day_open.time() or slot_time > latest_start.time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Times can only be blocked during clinic operating hours.',
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


@router.get('/clinic-hours', response_model=ClinicHoursResponse)
def get_clinic_hours(db: Session = Depends(get_db)):
    """Return the currently-configured weekly hours and upcoming holiday closures."""
    ensure_database_ready()

    try:
        daily_hours_map = get_daily_hours_map(db)
        holiday_lookup = get_holiday_lookup(db)

        return ClinicHoursResponse(
            daily_hours=[daily_hours_map[day] for day in range(7)],
            holidays=list(holiday_lookup.values()),
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.put('/clinic-hours', response_model=ClinicHoursResponse)
def update_clinic_hours(data: UpdateClinicHoursRequest, db: Session = Depends(get_db)):
    """Replace the entire weekly schedule and holiday list (admin only)."""
    ensure_database_ready()

    try:
        db.query(ClinicHours).delete()
        db.query(ClinicHoliday).delete()

        daily_hours_rows: list[ClinicHours] = []
        for day in data.daily_hours:
            row = ClinicHours(
                day_of_week=day.day_of_week,
                is_open=day.is_open,
                open_time=day.open_time if day.is_open else None,
                close_time=day.close_time if day.is_open else None,
            )
            daily_hours_rows.append(row)
            db.add(row)

        holiday_rows: list[ClinicHoliday] = []
        for holiday in data.holidays:
            holiday_row = ClinicHoliday(
                holiday_date=holiday.holiday_date,
                name=holiday.name,
                is_annual=holiday.is_annual,
            )
            holiday_rows.append(holiday_row)
            db.add(holiday_row)

        db.commit()

        for row in daily_hours_rows:
            db.refresh(row)
        for row in holiday_rows:
            db.refresh(row)

        return ClinicHoursResponse(
            daily_hours=[
                DailyHoursSettingResponse(
                    day_of_week=row.day_of_week,
                    day_name=DAY_NAMES[row.day_of_week],
                    is_open=bool(row.is_open),
                    open_time=row.open_time,
                    close_time=row.close_time,
                )
                for row in sorted(daily_hours_rows, key=lambda item: item.day_of_week)
            ],
            holidays=[
                HolidaySettingResponse(
                    id=row.id,
                    holiday_date=row.holiday_date,
                    name=row.name,
                    is_annual=bool(row.is_annual),
                )
                for row in sorted(holiday_rows, key=lambda item: item.holiday_date)
            ],
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.post('/slots', response_model=BlockedTimeResponse, status_code=status.HTTP_201_CREATED)
def create_blocked_time(data: CreateBlockedTimeRequest, db: Session = Depends(get_db)):
    """Block a single 15-minute slot so it cannot be booked (admin only)."""
    ensure_database_ready()

    try:
        daily_hours_map = get_daily_hours_map(db)
        holiday_lookup = get_holiday_lookup(db)
        annual_holidays = get_annual_holiday_pairs(holiday_lookup)
        start_time, end_time = validate_slot_datetime(data.date, data.time, daily_hours_map, holiday_lookup, annual_holidays)

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
    """Unblock a previously-blocked slot by id (admin only)."""
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
    """Return every upcoming admin-blocked slot, ordered by start time."""
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
    """Generate every open 15-minute slot across the next ``SLOT_RANGE_DAYS`` days.

    Slots that are already booked, admin-blocked, inside the lunch closure, or
    fall on non-operating days are filtered out. The ``students_only`` query
    parameter is accepted for backwards compatibility and currently has no
    effect on the generated list.
    """
    del students_only
    ensure_database_ready()

    try:
        now = datetime.now()
        range_end = now + timedelta(days=SLOT_RANGE_DAYS)
        daily_hours_map = get_daily_hours_map(db)
        holiday_lookup = get_holiday_lookup(db)
        annual_holidays = get_annual_holiday_pairs(holiday_lookup)

        blocked_start_times = get_blocked_slot_starts(now, range_end, db)
        booked_start_times = get_booked_slot_starts(now, range_end, db)

        generated_slots: list[AvailabilitySlotResponse] = []
        current_day = date.today()
        generated_id = -1

        while current_day <= range_end.date():
            day_bounds = get_clinic_day_bounds(current_day, daily_hours_map, holiday_lookup, annual_holidays)
            if day_bounds:
                day_open, day_close = day_bounds
                current_start = day_open
                last_start = day_close - timedelta(minutes=DEFAULT_SLOT_DURATION_MINUTES)

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
def list_appointment_types(db: Session = Depends(get_db)):
    """Return every appointment type option alongside its duration in minutes."""
    ensure_database_ready()

    try:
        return [
            AppointmentTypeOptionResponse(
                id=option.id,
                appointment_type=option.appointment_type,
                duration_minutes=option.duration_minutes,
            )
            for option in db.query(AppointmentTypeOption).order_by(
                AppointmentTypeOption.appointment_type.asc()
            ).all()
            if option.appointment_type and option.duration_minutes
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.post('/appointment-types', response_model=AppointmentTypeOptionResponse, status_code=status.HTTP_201_CREATED)
def create_appointment_type(data: CreateAppointmentTypeRequest, db: Session = Depends(get_db)):
    """Create a new appointment type (admin only). Returns 409 on duplicates."""
    ensure_database_ready()

    try:
        existing = next(
            (
                option for option in db.query(AppointmentTypeOption).all()
                if normalize_stored_appointment_type_name(option.appointment_type) == data.appointment_type
            ),
            None,
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='That appointment type is already on the list. Try a different name.',
            )

        option = AppointmentTypeOption(
            appointment_type=data.appointment_type,
            duration_minutes=data.duration_minutes,
        )
        db.add(option)
        db.commit()
        db.refresh(option)

        return AppointmentTypeOptionResponse(
            id=option.id,
            appointment_type=option.appointment_type,
            duration_minutes=option.duration_minutes,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


def delete_appointment_type_by_identifier(
    admin_email: str,
    db: Session,
    appointment_type: str | None = None,
    appointment_type_id: int | None = None,
):
    """Delete an appointment type by id or name and return a diff of impacted appointments.

    Callable from multiple route shapes (query string, path, request body) so
    the admin UI can route the same intent through whichever method fits the
    client. Lookups tolerate mixed spelling via ``get_appointment_type_lookup_keys``.
    """
    normalized_email = admin_email.strip().lower()
    if not normalized_email.endswith('@admin.edu'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only admins can delete appointment types.',
        )

    ensure_database_ready()

    try:
        option = None

        if appointment_type_id is not None:
            option = db.query(AppointmentTypeOption).filter(
                AppointmentTypeOption.id == appointment_type_id
            ).first()

        if option is None and appointment_type:
            requested_keys = get_appointment_type_lookup_keys(appointment_type)
            option = next(
                (
                    stored_option for stored_option in db.query(AppointmentTypeOption).all()
                    if get_appointment_type_lookup_keys(stored_option.appointment_type) & requested_keys
                ),
                None,
            )

        if option is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Appointment type not found.',
            )

        deleted_type_keys = get_appointment_type_lookup_keys(option.appointment_type)
        now = datetime.now()
        upcoming_appointments = [
            appointment for appointment in db.query(Appointment).filter(
                Appointment.start_time.is_not(None),
                Appointment.end_time.is_not(None),
                Appointment.end_time > now,
            ).order_by(Appointment.start_time.asc()).all()
            if get_appointment_type_lookup_keys(appointment.appointment_type) & deleted_type_keys
        ]

        deleted_type = AppointmentTypeOptionResponse(
            id=option.id,
            appointment_type=option.appointment_type,
            duration_minutes=option.duration_minutes,
        )
        response = DeleteAppointmentTypeResponse(
            deleted_type=deleted_type,
            upcoming_appointments=[to_appointment_response(appointment) for appointment in upcoming_appointments],
        )

        db.delete(option)
        db.commit()
        return response
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.delete('/appointment-types', response_model=DeleteAppointmentTypeResponse)
def delete_appointment_type_from_query(
    appointment_type: str = Query(...),
    admin_email: str = Query(...),
    db: Session = Depends(get_db),
):
    return delete_appointment_type_by_identifier(
        appointment_type=appointment_type,
        admin_email=admin_email,
        db=db,
    )


@router.post('/appointment-types/delete', response_model=DeleteAppointmentTypeResponse)
@router.post('/appointment-types/delete/', response_model=DeleteAppointmentTypeResponse)
def delete_appointment_type_from_body(
    data: DeleteAppointmentTypeRequest,
    db: Session = Depends(get_db),
):
    return delete_appointment_type_by_identifier(
        appointment_type=data.appointment_type,
        appointment_type_id=data.appointment_type_id,
        admin_email=data.admin_email,
        db=db,
    )


@router.delete('/appointment-types/{appointment_type}', response_model=DeleteAppointmentTypeResponse)
def delete_appointment_type(
    appointment_type: str,
    admin_email: str = Query(...),
    db: Session = Depends(get_db),
):
    return delete_appointment_type_by_identifier(
        appointment_type=appointment_type,
        admin_email=admin_email,
        db=db,
    )


@router.get('/calendar', response_model=list[CalendarSlotResponse])
def list_calendar_slots(
    days: int = Query(default=14, ge=1, le=14),
    appointment_type: str = Query(...),
    db: Session = Depends(get_db),
):
    """Return every bookable start time for a given appointment type.

    Walks each open day inside the requested window (up to 14 days) and emits
    a start every 15 minutes as long as the full duration of the requested
    type fits without overlapping a booked, blocked, or lunch slot.
    """
    ensure_database_ready()

    try:
        duration_map = get_appointment_duration_map(db)
        normalized_appointment_type = appointment_type.strip().lower()
        if not is_appointment_type_supported(normalized_appointment_type, duration_map):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid appointment type.',
            )

        duration_minutes = duration_map[normalized_appointment_type]
        now = datetime.now()
        range_end = now + timedelta(days=days)
        daily_hours_map = get_daily_hours_map(db)
        holiday_lookup = get_holiday_lookup(db)
        annual_holidays = get_annual_holiday_pairs(holiday_lookup)
        blocked_start_times = get_blocked_slot_starts(now, range_end, db)
        booked_start_times = get_booked_slot_starts(now, range_end, db)

        calendar_slots: list[CalendarSlotResponse] = []
        current_day = date.today()

        while current_day <= range_end.date():
            day_bounds = get_clinic_day_bounds(current_day, daily_hours_map, holiday_lookup, annual_holidays)
            if day_bounds:
                day_open, day_close = day_bounds
                current_start = day_open
                latest_possible_start = day_close - timedelta(minutes=duration_minutes)

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


@router.get('/appointments/mine', response_model=list[AppointmentResponse])
def list_my_appointments(
    student_email: str = Query(...),
    db: Session = Depends(get_db),
):
    """Return the caller's upcoming appointments (students only, case-insensitive match)."""
    normalized_email = student_email.strip().lower()
    if not normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Student email is required.',
        )

    if normalized_email.endswith('@admin.edu'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only students can view their own appointments.',
        )

    ensure_database_ready()

    try:
        duration_map = get_appointment_duration_map(db)
        now = datetime.now()
        appointments = db.query(Appointment).filter(
            func.lower(func.trim(Appointment.student_email)) == normalized_email,
            Appointment.start_time.is_not(None),
            Appointment.end_time.is_not(None),
            Appointment.end_time > now,
        ).order_by(Appointment.start_time.asc()).all()

        return [to_appointment_response(appointment, duration_map) for appointment in appointments]
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
    """Return every upcoming appointment across the clinic (admin only)."""
    normalized_email = admin_email.strip().lower()
    if not normalized_email.endswith('@admin.edu'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only admins can view booked appointments.',
        )

    ensure_database_ready()

    try:
        duration_map = get_appointment_duration_map(db)
        now = datetime.now()
        appointments = db.query(Appointment).filter(
            Appointment.start_time.is_not(None),
            Appointment.end_time.is_not(None),
            Appointment.end_time > now,
        ).order_by(Appointment.start_time.asc()).all()

        return [to_appointment_response(appointment, duration_map) for appointment in appointments]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.delete('/appointments/{appointment_id}', status_code=status.HTTP_204_NO_CONTENT)
def cancel_my_appointment(
    appointment_id: int,
    student_email: str = Query(...),
    db: Session = Depends(get_db),
):
    """Cancel the caller's own appointment. Only the student who booked it may cancel."""
    normalized_email = student_email.strip().lower()
    if not normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Student email is required.',
        )

    if normalized_email.endswith('@admin.edu'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only students can cancel their own appointments.',
        )

    ensure_database_ready()

    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Appointment not found.',
            )

        appointment_owner_email = (appointment.student_email or '').strip().lower()
        if appointment_owner_email != normalized_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Only the student who booked this appointment can cancel it.',
            )

        db.delete(appointment)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.post('/appointments', response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(data: CreateAppointmentRequest, db: Session = Depends(get_db)):
    """Book a new appointment for a student.

    Validates the requested window, then rejects with 409 if the slot is
    already admin-blocked or booked by another student.
    """
    ensure_database_ready()

    try:
        duration_map = get_appointment_duration_map(db)
        daily_hours_map = get_daily_hours_map(db)
        holiday_lookup = get_holiday_lookup(db)
        annual_holidays = get_annual_holiday_pairs(holiday_lookup)
        if data.appointment_type not in duration_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid appointment type.',
            )

        duration_minutes = duration_map[data.appointment_type]
        start_time = data.start_time.replace(second=0, microsecond=0)
        now = datetime.now()
        end_time = validate_appointment_window(
            start_time,
            duration_minutes,
            now,
            daily_hours_map,
            holiday_lookup,
            annual_holidays,
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


@router.patch('/appointments/{appointment_id}/reschedule', response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: int,
    data: RescheduleAppointmentRequest,
    db: Session = Depends(get_db),
):
    """Move an upcoming appointment to a new start time (owning student only)."""
    ensure_database_ready()

    try:
        duration_map = get_appointment_duration_map(db)
        daily_hours_map = get_daily_hours_map(db)
        holiday_lookup = get_holiday_lookup(db)
        annual_holidays = get_annual_holiday_pairs(holiday_lookup)
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Appointment not found.',
            )

        appointment_owner_email = (appointment.student_email or '').strip().lower()
        if appointment_owner_email != data.student_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You can only reschedule your own appointments.',
            )

        now = datetime.now()
        if appointment.end_time and appointment.end_time <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Only upcoming appointments can be rescheduled.',
            )

        duration_minutes = get_appointment_duration_minutes(appointment, duration_map)
        start_time = data.start_time.replace(second=0, microsecond=0)
        end_time = validate_appointment_window(
            start_time,
            duration_minutes,
            now,
            daily_hours_map,
            holiday_lookup,
            annual_holidays,
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

        overlapping_appointment = db.query(Appointment).filter(
            Appointment.id != appointment_id,
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        ).first()
        if overlapping_appointment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='This time is already booked.',
            )

        appointment.start_time = start_time
        appointment.end_time = end_time
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        return to_appointment_response(appointment, duration_map)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.patch('/appointments/{appointment_id}/notes', response_model=AppointmentResponse)
def update_appointment_notes(
    appointment_id: int,
    data: UpdateAppointmentNotesRequest,
    db: Session = Depends(get_db),
):
    """Update free-text notes on the caller's own upcoming appointment."""
    ensure_database_ready()

    try:
        duration_map = get_appointment_duration_map(db)
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Appointment not found.',
            )

        student_email = (appointment.student_email or '').strip().lower()
        if student_email != data.student_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You can only update notes for your own appointments.',
            )

        if appointment.end_time and appointment.end_time <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Only upcoming appointments can be updated.',
            )

        appointment.notes = data.notes
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        return to_appointment_response(appointment, duration_map)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc


@router.get('/appointments/{appointment_id}/ics')
def download_appointment_ics(
    appointment_id: int,
    student_email: str = Query(...),
    db: Session = Depends(get_db),
):
    """Stream an ``.ics`` calendar file for the caller's appointment."""
    normalized_email = student_email.strip().lower()
    if not normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Student email is required.',
        )

    if normalized_email.endswith('@admin.edu'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only students can download appointment calendar files.',
        )

    ensure_database_ready()

    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Appointment not found.',
            )

        appointment_owner_email = (appointment.student_email or '').strip().lower()
        if appointment_owner_email != normalized_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You can only download calendar files for your own appointments.',
            )

        summary = format_calendar_summary_from_type(appointment.appointment_type)
        ics_payload = create_appointment_ics(appointment, summary)
        filename = f'lynx-health-appointment-{appointment_id}.ics'
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return Response(content=ics_payload, media_type='text/calendar; charset=utf-8', headers=headers)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable. Verify DATABASE_URL and Postgres credentials.',
        ) from exc
