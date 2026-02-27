import os
from datetime import date, datetime, time, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault('DATABASE_URL', 'sqlite:///./test.db')

from backend.routes import availability_routes  # noqa: E402
from backend.database import Base  # noqa: E402
from backend.models.appointment import Appointment  # noqa: E402
from backend.models.availability import Availability  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.routes.availability_routes import (  # noqa: E402
    CreateAppointmentRequest,
    CreateBlockedTimeRequest,
    UpdateAppointmentNotesRequest,
    cancel_my_appointment,
    get_booked_slot_starts,
    iterate_slot_starts,
    list_appointments,
    list_my_appointments,
    update_appointment_notes,
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


@pytest.fixture
def appointment_db():
    engine = create_engine('sqlite:///:memory:')
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[User.__table__, Availability.__table__, Appointment.__table__])

    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine, tables=[Appointment.__table__, Availability.__table__, User.__table__])


def test_cancel_my_appointment_rejects_blank_student_email(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    with pytest.raises(HTTPException) as exception_info:
        cancel_my_appointment(appointment_id=1, student_email='   ', db=appointment_db)

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == 'Student email is required.'


def test_cancel_my_appointment_rejects_admin_email(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    with pytest.raises(HTTPException) as exception_info:
        cancel_my_appointment(appointment_id=1, student_email='admin@admin.edu', db=appointment_db)

    assert exception_info.value.status_code == 403
    assert exception_info.value.detail == 'Only students can cancel their own appointments.'


def test_cancel_my_appointment_returns_not_found_when_missing(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    with pytest.raises(HTTPException) as exception_info:
        cancel_my_appointment(appointment_id=999, student_email='student@example.edu', db=appointment_db)

    assert exception_info.value.status_code == 404
    assert exception_info.value.detail == 'Appointment not found.'


def test_cancel_my_appointment_rejects_non_owner(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    appointment = Appointment(
        student_email='owner@example.edu',
        appointment_type='testing',
        start_time=datetime(2026, 1, 5, 10, 0),
        end_time=datetime(2026, 1, 5, 10, 30),
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    with pytest.raises(HTTPException) as exception_info:
        cancel_my_appointment(
            appointment_id=appointment.id,
            student_email='other@example.edu',
            db=appointment_db,
        )

    assert exception_info.value.status_code == 403
    assert exception_info.value.detail == 'Only the student who booked this appointment can cancel it.'


def test_cancel_my_appointment_hard_deletes_owner_appointment(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    appointment = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=datetime(2026, 1, 5, 11, 0),
        end_time=datetime(2026, 1, 5, 11, 30),
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    cancel_my_appointment(
        appointment_id=appointment.id,
        student_email='student@example.edu',
        db=appointment_db,
    )

    deleted = appointment_db.query(Appointment).filter(Appointment.id == appointment.id).first()
    assert deleted is None


def test_cancel_my_appointment_reopens_slot_in_booked_slot_lookup(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    start_time = datetime(2026, 1, 5, 9, 0)
    end_time = datetime(2026, 1, 5, 9, 30)
    appointment = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=start_time,
        end_time=end_time,
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    booked_before_cancel = get_booked_slot_starts(
        now=datetime(2026, 1, 5, 8, 0),
        range_end=datetime(2026, 1, 6, 0, 0),
        db=appointment_db,
    )
    assert datetime(2026, 1, 5, 9, 0) in booked_before_cancel
    assert datetime(2026, 1, 5, 9, 15) in booked_before_cancel

    cancel_my_appointment(
        appointment_id=appointment.id,
        student_email='student@example.edu',
        db=appointment_db,
    )

    booked_after_cancel = get_booked_slot_starts(
        now=datetime(2026, 1, 5, 8, 0),
        range_end=datetime(2026, 1, 6, 0, 0),
        db=appointment_db,
    )
    assert datetime(2026, 1, 5, 9, 0) not in booked_after_cancel
    assert datetime(2026, 1, 5, 9, 15) not in booked_after_cancel


class _FakeQuery:
    def __init__(self, appointments: list[Appointment]):
        self._appointments = appointments

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._appointments[0] if self._appointments else None

    def all(self):
        return list(self._appointments)


class _FakeDb:
    def __init__(self, appointments: list[Appointment] | Appointment | None):
        if isinstance(appointments, list):
            self.appointments = appointments
        elif appointments is None:
            self.appointments = []
        else:
            self.appointments = [appointments]
        self.committed = False

    def query(self, _model):
        return _FakeQuery(self.appointments)

    def add(self, _obj):
        return None

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        return None

    def rollback(self):
        return None


def _build_appointment(student_email: str, *, is_upcoming: bool = True) -> Appointment:
    now = datetime.now()
    start_time = now + timedelta(hours=1)
    end_time = now + timedelta(hours=2)
    if not is_upcoming:
        start_time = now - timedelta(hours=2)
        end_time = now - timedelta(hours=1)

    appointment = Appointment(
        id=100,
        student_email=student_email,
        appointment_type='testing',
        start_time=start_time,
        end_time=end_time,
        status='booked',
        notes='Initial',
    )
    return appointment


def test_update_appointment_notes_updates_matching_upcoming_appointment(monkeypatch) -> None:
    monkeypatch.setattr(availability_routes, 'ensure_database_ready', lambda: None)
    appointment = _build_appointment('student@example.edu', is_upcoming=True)
    db = _FakeDb(appointment)

    payload = UpdateAppointmentNotesRequest(student_email='student@example.edu', notes='Updated note')
    response = update_appointment_notes(appointment_id=100, data=payload, db=db)

    assert db.committed is True
    assert appointment.notes == 'Updated note'
    assert response.notes == 'Updated note'


def test_update_appointment_notes_rejects_non_owner(monkeypatch) -> None:
    monkeypatch.setattr(availability_routes, 'ensure_database_ready', lambda: None)
    appointment = _build_appointment('other@example.edu', is_upcoming=True)
    db = _FakeDb(appointment)

    payload = UpdateAppointmentNotesRequest(student_email='student@example.edu', notes='Updated note')

    with pytest.raises(HTTPException) as exception_info:
        update_appointment_notes(appointment_id=100, data=payload, db=db)

    assert exception_info.value.status_code == 403
    assert exception_info.value.detail == 'You can only update notes for your own appointments.'


def test_update_appointment_notes_rejects_past_appointment(monkeypatch) -> None:
    monkeypatch.setattr(availability_routes, 'ensure_database_ready', lambda: None)
    appointment = _build_appointment('student@example.edu', is_upcoming=False)
    db = _FakeDb(appointment)

    payload = UpdateAppointmentNotesRequest(student_email='student@example.edu', notes='Updated note')

    with pytest.raises(HTTPException) as exception_info:
        update_appointment_notes(appointment_id=100, data=payload, db=db)

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == 'Only upcoming appointments can be updated.'


def test_updated_notes_are_visible_to_user_and_admin_views(monkeypatch) -> None:
    monkeypatch.setattr(availability_routes, 'ensure_database_ready', lambda: None)
    appointment = _build_appointment('student@example.edu', is_upcoming=True)
    db = _FakeDb(appointment)

    payload = UpdateAppointmentNotesRequest(student_email='student@example.edu', notes='Shared update')
    update_appointment_notes(appointment_id=100, data=payload, db=db)

    student_appointments = list_my_appointments(student_email='student@example.edu', db=db)
    admin_appointments = list_appointments(admin_email='admin@admin.edu', db=db)

    assert student_appointments[0].notes == 'Shared update'
    assert admin_appointments[0].notes == 'Shared update'
