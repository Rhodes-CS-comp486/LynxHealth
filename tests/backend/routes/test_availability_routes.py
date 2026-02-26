import os
from datetime import date, datetime, time

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

os.environ.setdefault('DATABASE_URL', 'sqlite:///./test.db')

from backend.routes.availability_routes import (  # noqa: E402
    CreateAppointmentRequest,
    CreateBlockedTimeRequest,
    UpdateAppointmentNotesRequest,
    iterate_slot_starts,
    list_my_appointments,
    validate_slot_datetime,
)


def test_create_blocked_time_request_normalizes_admin_email() -> None:
    request = CreateBlockedTimeRequest(admin_email=' ADMIN@ADMIN.EDU ', date=date(2026, 1, 5), time=time(9, 0))

    assert request.admin_email == 'admin@admin.edu'


def test_create_blocked_time_request_rejects_non_admin_email() -> None:
    with pytest.raises(ValidationError):
        CreateBlockedTimeRequest(admin_email='student@example.edu', date=date(2026, 1, 5), time=time(9, 0))


def test_create_appointment_request_normalizes_fields() -> None:
    request = CreateAppointmentRequest(
        student_email=' STUDENT@EXAMPLE.EDU ',
        appointment_type=' Testing ',
        start_time=datetime(2026, 1, 5, 9, 0),
    )

    assert request.student_email == 'student@example.edu'
    assert request.appointment_type == 'testing'


def test_update_appointment_notes_request_normalizes_fields() -> None:
    request = UpdateAppointmentNotesRequest(student_email=' STUDENT@EXAMPLE.EDU ', notes='  updated notes  ')

    assert request.student_email == 'student@example.edu'
    assert request.notes == 'updated notes'


def test_update_appointment_notes_request_rejects_admin_email() -> None:
    with pytest.raises(ValidationError):
        UpdateAppointmentNotesRequest(student_email='admin@admin.edu', notes='a')


def test_iterate_slot_starts_rounds_up_to_next_interval() -> None:
    slots = iterate_slot_starts(datetime(2026, 1, 5, 9, 2), datetime(2026, 1, 5, 9, 50))

    assert slots == {
        datetime(2026, 1, 5, 9, 15),
        datetime(2026, 1, 5, 9, 30),
        datetime(2026, 1, 5, 9, 45),
    }


def test_validate_slot_datetime_returns_time_bounds_for_valid_slot() -> None:
    start, end = validate_slot_datetime(date(2026, 1, 5), time(9, 0))

    assert start == datetime(2026, 1, 5, 9, 0)
    assert end == datetime(2026, 1, 5, 9, 15)


@pytest.mark.parametrize(
    ('slot_date', 'slot_time', 'error_detail'),
    [
        (date(2026, 1, 4), time(9, 0), 'Times can only be blocked on weekdays (Monday through Friday).'),
        (date(2026, 1, 5), time(8, 45), 'Times can only be blocked between 9:00 AM and 3:45 PM.'),
        (date(2026, 1, 5), time(9, 10), 'Times must be on 15-minute boundaries.'),
        (date(2026, 1, 5), time(12, 0), '12:00 PM to 1:00 PM is reserved for lunch and is always blocked.'),
    ],
)
def test_validate_slot_datetime_rejects_invalid_slots(slot_date: date, slot_time: time, error_detail: str) -> None:
    with pytest.raises(HTTPException) as exception_info:
        validate_slot_datetime(slot_date, slot_time)

    assert exception_info.value.detail == error_detail


def test_list_my_appointments_rejects_blank_student_email() -> None:
    with pytest.raises(HTTPException) as exception_info:
        list_my_appointments(student_email='   ', db=None)

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == 'Student email is required.'


def test_list_my_appointments_rejects_admin_email() -> None:
    with pytest.raises(HTTPException) as exception_info:
        list_my_appointments(student_email='admin@admin.edu', db=None)

    assert exception_info.value.status_code == 403
    assert exception_info.value.detail == 'Only students can view their own appointments.'
