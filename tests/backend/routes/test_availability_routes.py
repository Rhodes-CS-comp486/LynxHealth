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
from backend.models.appointment_type_option import AppointmentTypeOption  # noqa: E402
from backend.models.availability import Availability  # noqa: E402
from backend.models.clinic_holiday import ClinicHoliday  # noqa: E402
from backend.models.clinic_hours import ClinicHours  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.routes.availability_routes import (  # noqa: E402
    DailyHoursSettingResponse,
    HolidaySettingResponse,
    CreateAppointmentRequest,
    CreateAppointmentTypeRequest,
    DeleteAppointmentTypeRequest,
    CreateBlockedTimeRequest,
    UpdateAppointmentNotesRequest,
    cancel_my_appointment,
    create_appointment_type,
    delete_appointment_type,
    delete_appointment_type_from_body,
    delete_appointment_type_from_query,
    create_appointment_ics,
    download_appointment_ics,
    format_calendar_summary_from_type,
    get_booked_slot_starts,
    iterate_slot_starts,
    list_appointments,
    list_appointment_types,
    list_availability_slots,
    list_calendar_slots,
    list_my_appointments,
    reschedule_appointment,
    update_appointment_notes,
    validate_appointment_window,
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


def test_create_appointment_type_request_normalizes_fields() -> None:
    request = CreateAppointmentTypeRequest(
        admin_email=' ADMIN@ADMIN.EDU ',
        appointment_type=' Physical Exam ',
        duration_minutes=45,
    )

    assert request.admin_email == 'admin@admin.edu'
    assert request.appointment_type == 'physical_exam'
    assert request.duration_minutes == 45


def test_create_appointment_type_request_allows_hyphens() -> None:
    request = CreateAppointmentTypeRequest(
        admin_email='admin@admin.edu',
        appointment_type=' Check-Up ',
        duration_minutes=30,
    )

    assert request.appointment_type == 'check-up'


def test_create_appointment_type_request_rejects_unsupported_punctuation() -> None:
    with pytest.raises(ValidationError) as exception_info:
        CreateAppointmentTypeRequest(
            admin_email='admin@admin.edu',
            appointment_type='Check-Up!',
            duration_minutes=30,
        )

    assert "Please use only letters, numbers, spaces, or hyphens in the type name. Remove '!'." in str(exception_info.value)


def test_create_appointment_type_request_rejects_non_admin() -> None:
    with pytest.raises(ValidationError):
        CreateAppointmentTypeRequest(
            admin_email='student@example.edu',
            appointment_type='physical exam',
            duration_minutes=45,
        )


def test_delete_appointment_type_request_allows_stored_slugs() -> None:
    request = DeleteAppointmentTypeRequest(
        admin_email=' ADMIN@ADMIN.EDU ',
        appointment_type=' physical_exam ',
    )

    assert request.admin_email == 'admin@admin.edu'
    assert request.appointment_type == 'physical_exam'


def test_delete_appointment_type_request_rejects_non_admin() -> None:
    with pytest.raises(ValidationError):
        DeleteAppointmentTypeRequest(
            admin_email='student@example.edu',
            appointment_type='physical_exam',
        )


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
        (date(2026, 1, 4), time(9, 0), 'Times can only be blocked on clinic operating days.'),
        (date(2026, 1, 5), time(8, 45), 'Times can only be blocked during clinic operating hours.'),
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
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            Availability.__table__,
            Appointment.__table__,
            AppointmentTypeOption.__table__,
            ClinicHours.__table__,
            ClinicHoliday.__table__,
        ],
    )

    db = testing_session_local()
    try:
        _seed_appointment_types(db)
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                ClinicHoliday.__table__,
                ClinicHours.__table__,
                AppointmentTypeOption.__table__,
                Appointment.__table__,
                Availability.__table__,
                User.__table__,
            ],
        )


def _seed_appointment_types(db) -> None:
    db.add_all([
        AppointmentTypeOption(appointment_type='immunization', duration_minutes=15),
        AppointmentTypeOption(appointment_type='testing', duration_minutes=30),
        AppointmentTypeOption(appointment_type='counseling', duration_minutes=60),
        AppointmentTypeOption(appointment_type='other', duration_minutes=60),
        AppointmentTypeOption(appointment_type='prescription', duration_minutes=15),
    ])
    db.commit()


def test_list_appointment_types_returns_database_values(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    response = list_appointment_types(db=appointment_db)

    assert {option.appointment_type for option in response} >= {
        'immunization',
        'testing',
        'counseling',
        'other',
        'prescription',
    }


def test_create_appointment_type_persists_new_option_for_admin(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    payload = CreateAppointmentTypeRequest(
        admin_email='admin@admin.edu',
        appointment_type='physical exam',
        duration_minutes=45,
    )
    response = create_appointment_type(data=payload, db=appointment_db)

    assert response.appointment_type == 'physical_exam'
    assert response.duration_minutes == 45

    options = list_appointment_types(db=appointment_db)
    assert any(option.appointment_type == 'physical_exam' and option.duration_minutes == 45 for option in options)


def test_create_appointment_type_persists_hyphenated_option_for_admin(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    payload = CreateAppointmentTypeRequest(
        admin_email='admin@admin.edu',
        appointment_type='check-up',
        duration_minutes=30,
    )
    response = create_appointment_type(data=payload, db=appointment_db)

    assert response.appointment_type == 'check-up'
    assert response.duration_minutes == 30

    options = list_appointment_types(db=appointment_db)
    assert any(option.appointment_type == 'check-up' and option.duration_minutes == 30 for option in options)


def test_delete_appointment_type_removes_option_and_returns_upcoming_appointments(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    now = datetime.now().replace(second=0, microsecond=0)
    upcoming = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, minutes=30),
        status='booked',
        notes='Bring prior records',
    )
    appointment_db.add(upcoming)
    appointment_db.commit()

    response = delete_appointment_type(
        appointment_type='testing',
        admin_email='admin@admin.edu',
        db=appointment_db,
    )

    assert response.deleted_type.appointment_type == 'testing'
    assert response.deleted_type.duration_minutes == 30
    assert len(response.upcoming_appointments) == 1
    assert response.upcoming_appointments[0].student_email == 'student@example.edu'

    options = list_appointment_types(db=appointment_db)
    assert all(option.appointment_type != 'testing' for option in options)


def test_delete_appointment_type_accepts_stored_slug_with_underscores(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    option = AppointmentTypeOption(appointment_type='physical_exam', duration_minutes=45)
    appointment_db.add(option)
    appointment_db.commit()

    response = delete_appointment_type(
        appointment_type='physical_exam',
        admin_email='admin@admin.edu',
        db=appointment_db,
    )

    assert response.deleted_type.appointment_type == 'physical_exam'
    options = list_appointment_types(db=appointment_db)
    assert all(option.appointment_type != 'physical_exam' for option in options)


def test_delete_appointment_type_matches_legacy_spaced_name(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    legacy_option = appointment_db.query(AppointmentTypeOption).filter_by(appointment_type='testing').first()
    assert legacy_option is not None
    legacy_option.appointment_type = 'Physical Exam'

    now = datetime.now().replace(second=0, microsecond=0)
    upcoming = Appointment(
        student_email='student@example.edu',
        appointment_type='Physical Exam',
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, minutes=45),
        status='booked',
        notes='Legacy appointment type formatting',
    )
    appointment_db.add(upcoming)
    appointment_db.commit()

    response = delete_appointment_type(
        appointment_type='physical exam',
        admin_email='admin@admin.edu',
        db=appointment_db,
    )

    assert response.deleted_type.appointment_type == 'Physical Exam'
    assert len(response.upcoming_appointments) == 1
    assert response.upcoming_appointments[0].appointment_type == 'Physical Exam'


def test_delete_appointment_type_from_query_handles_spaced_names(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    legacy_option = appointment_db.query(AppointmentTypeOption).filter_by(appointment_type='testing').first()
    assert legacy_option is not None
    legacy_option.appointment_type = 'Physical Exam'
    appointment_db.commit()

    response = delete_appointment_type_from_query(
        appointment_type='physical_exam',
        admin_email='admin@admin.edu',
        db=appointment_db,
    )

    assert response.deleted_type.appointment_type == 'Physical Exam'
    options = list_appointment_types(db=appointment_db)
    assert all(option.appointment_type != 'Physical Exam' for option in options)


def test_delete_appointment_type_from_body_handles_stored_slugs(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    option = AppointmentTypeOption(appointment_type='physical_exam', duration_minutes=45)
    appointment_db.add(option)
    appointment_db.commit()

    payload = DeleteAppointmentTypeRequest(
        appointment_type='physical_exam',
        admin_email='admin@admin.edu',
    )
    response = delete_appointment_type_from_body(
        data=payload,
        db=appointment_db,
    )

    assert response.deleted_type.appointment_type == 'physical_exam'
    options = list_appointment_types(db=appointment_db)
    assert all(option.appointment_type != 'physical_exam' for option in options)


def test_delete_appointment_type_rejects_non_admin(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    with pytest.raises(HTTPException) as exception_info:
        delete_appointment_type(
            appointment_type='testing',
            admin_email='student@example.edu',
            db=appointment_db,
        )

    assert exception_info.value.status_code == 403
    assert exception_info.value.detail == 'Only admins can delete appointment types.'


def test_create_appointment_type_rejects_duplicate_legacy_spaced_name(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    legacy_option = appointment_db.query(AppointmentTypeOption).filter_by(appointment_type='testing').first()
    assert legacy_option is not None
    legacy_option.appointment_type = 'Physical Exam'
    appointment_db.commit()

    payload = CreateAppointmentTypeRequest(
        admin_email='admin@admin.edu',
        appointment_type='physical exam',
        duration_minutes=45,
    )

    with pytest.raises(HTTPException) as exception_info:
        create_appointment_type(payload, db=appointment_db)

    assert exception_info.value.status_code == 409
    assert exception_info.value.detail == 'That appointment type is already on the list. Try a different name.'


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


def test_create_appointment_ics_contains_event_fields() -> None:
    appointment = Appointment(
        id=77,
        student_email='student@example.edu',
        appointment_type='testing',
        notes='Bring ID card',
        start_time=datetime(2026, 1, 5, 9, 0),
        end_time=datetime(2026, 1, 5, 9, 30),
        status='booked',
    )

    payload = create_appointment_ics(appointment, 'Health Center Appointment: Testing')

    assert 'BEGIN:VCALENDAR' in payload
    assert 'BEGIN:VEVENT' in payload
    assert 'UID:appointment-77@lynxhealth.local' in payload
    assert 'DTSTART:20260105T090000' in payload
    assert 'DTEND:20260105T093000' in payload
    assert 'SUMMARY:Health Center Appointment: Testing' in payload
    assert 'DESCRIPTION:Bring ID card' in payload


def test_format_calendar_summary_from_type_formats_human_readable_summary() -> None:
    assert format_calendar_summary_from_type('blood_pressure_follow_up') == 'Health Center Appointment: Blood Pressure Follow Up'
    assert format_calendar_summary_from_type(None) == 'Health Center Appointment: Appointment'


def test_download_appointment_ics_returns_calendar_attachment(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)
    appointment = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        notes='Bring forms',
        start_time=datetime(2026, 1, 5, 9, 0),
        end_time=datetime(2026, 1, 5, 9, 30),
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    response = download_appointment_ics(
        appointment_id=appointment.id,
        student_email='student@example.edu',
        db=appointment_db,
    )

    assert response.media_type == 'text/calendar; charset=utf-8'
    assert response.headers.get('content-disposition') == f'attachment; filename=\"lynx-health-appointment-{appointment.id}.ics\"'
    payload = response.body.decode('utf-8')
    assert 'BEGIN:VCALENDAR' in payload
    assert 'SUMMARY:Health Center Appointment: Testing' in payload


def test_download_appointment_ics_rejects_non_owner(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)
    appointment = Appointment(
        student_email='owner@example.edu',
        appointment_type='testing',
        notes='owner notes',
        start_time=datetime(2026, 1, 5, 9, 0),
        end_time=datetime(2026, 1, 5, 9, 30),
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    with pytest.raises(HTTPException) as exception_info:
        download_appointment_ics(
            appointment_id=appointment.id,
            student_email='other@example.edu',
            db=appointment_db,
        )

    assert exception_info.value.status_code == 403
    assert exception_info.value.detail == 'You can only download calendar files for your own appointments.'


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




def test_cancel_endpoint_reopens_public_slots_and_calendar(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    start_time = _next_weekday_from_now(hour=10, minute=0)
    appointment = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=start_time,
        end_time=start_time + timedelta(minutes=30),
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    slots_before = list_availability_slots(db=appointment_db)
    slot_starts_before = {slot.start_time for slot in slots_before}

    assert start_time not in slot_starts_before
    assert start_time + timedelta(minutes=15) not in slot_starts_before

    calendar_before = list_calendar_slots(days=14, appointment_type='testing', db=appointment_db)
    calendar_starts_before = {slot.start_time for slot in calendar_before}

    assert start_time not in calendar_starts_before

    cancel_my_appointment(
        appointment_id=appointment.id,
        student_email='student@example.edu',
        db=appointment_db,
    )

    slots_after = list_availability_slots(db=appointment_db)
    slot_starts_after = {slot.start_time for slot in slots_after}

    assert start_time in slot_starts_after
    assert start_time + timedelta(minutes=15) in slot_starts_after

    calendar_after = list_calendar_slots(days=14, appointment_type='testing', db=appointment_db)
    calendar_starts_after = {slot.start_time for slot in calendar_after}

    assert start_time in calendar_starts_after


def test_cancel_endpoint_removes_appointment_from_admin_listing(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    start_time = _next_weekday_from_now(hour=11, minute=0)
    appointment = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=start_time,
        end_time=start_time + timedelta(minutes=30),
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    admin_before = list_appointments(admin_email='admin@admin.edu', db=appointment_db)
    before_ids = {item.id for item in admin_before}
    assert appointment.id in before_ids

    cancel_my_appointment(
        appointment_id=appointment.id,
        student_email='student@example.edu',
        db=appointment_db,
    )

    admin_after = list_appointments(admin_email='admin@admin.edu', db=appointment_db)
    after_ids = {item.id for item in admin_after}
    assert appointment.id not in after_ids

    deleted = appointment_db.query(Appointment).filter(Appointment.id == appointment.id).first()
    assert deleted is None


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
        self.appointment_type_options: list[AppointmentTypeOption] = []
        self.committed = False

    def query(self, model):
        if model is AppointmentTypeOption:
            return _FakeQuery(self.appointment_type_options)
        return _FakeQuery(self.appointments)

    def add(self, _obj):
        return None

    def add_all(self, objects):
        self.appointment_type_options.extend(objects)

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        return None

    def rollback(self):
        return None




def _next_weekday_from_now(hour: int, minute: int) -> datetime:
    candidate = datetime.now().replace(second=0, microsecond=0) + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.replace(hour=hour, minute=minute)

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


def test_update_appointment_notes_returns_not_found_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(availability_routes, 'ensure_database_ready', lambda: None)
    db = _FakeDb(None)

    payload = UpdateAppointmentNotesRequest(student_email='student@example.edu', notes='Updated note')

    with pytest.raises(HTTPException) as exception_info:
        update_appointment_notes(appointment_id=999, data=payload, db=db)

    assert exception_info.value.status_code == 404
    assert exception_info.value.detail == 'Appointment not found.'


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


def test_validate_appointment_window_rejects_past_time() -> None:
    with pytest.raises(HTTPException) as exception_info:
        validate_appointment_window(
            datetime(2026, 1, 5, 9, 0),
            duration_minutes=30,
            now=datetime(2026, 1, 5, 9, 0),
        )

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == 'Appointments must be scheduled in the future.'


def test_validate_appointment_window_rejects_day_closed_by_holiday() -> None:
    daily_hours_map = {
        0: DailyHoursSettingResponse(day_of_week=0, day_name='Monday', is_open=True, open_time=time(9, 0), close_time=time(16, 0)),
    }
    with pytest.raises(HTTPException) as exception_info:
        validate_appointment_window(
            datetime(2026, 1, 5, 9, 0),
            duration_minutes=30,
            now=datetime(2026, 1, 4, 9, 0),
            daily_hours_map=daily_hours_map,
            holiday_lookup={date(2026, 1, 5): HolidaySettingResponse(holiday_date=date(2026, 1, 5), name='Holiday')},
        )

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == 'Appointments can only be scheduled on clinic operating days.'


def test_validate_appointment_window_rejects_day_closed_by_annual_holiday() -> None:
    daily_hours_map = {
        0: DailyHoursSettingResponse(day_of_week=0, day_name='Monday', is_open=True, open_time=time(9, 0), close_time=time(16, 0)),
    }
    with pytest.raises(HTTPException) as exception_info:
        validate_appointment_window(
            datetime(2027, 1, 4, 9, 0),
            duration_minutes=30,
            now=datetime(2027, 1, 3, 9, 0),
            daily_hours_map=daily_hours_map,
            holiday_lookup={},
            annual_holidays={(1, 4)},
        )

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == 'Appointments can only be scheduled on clinic operating days.'


def test_reschedule_appointment_updates_time_and_preserves_details(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    base_start = _next_weekday_from_now(hour=10, minute=0)
    original = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        notes='Bring prior results',
        start_time=base_start,
        end_time=base_start + timedelta(minutes=30),
        status='booked',
    )
    appointment_db.add(original)
    appointment_db.commit()
    appointment_db.refresh(original)

    new_start = base_start + timedelta(hours=1)
    payload = availability_routes.RescheduleAppointmentRequest(
        student_email='student@example.edu',
        start_time=new_start,
    )

    response = reschedule_appointment(appointment_id=original.id, data=payload, db=appointment_db)

    assert response.id == original.id
    assert response.start_time == new_start
    assert response.end_time == new_start + timedelta(minutes=30)
    assert response.appointment_type == 'testing'
    assert response.notes == 'Bring prior results'


def test_reschedule_appointment_reopens_old_slot_and_blocks_new_slot(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    base_start = _next_weekday_from_now(hour=9, minute=0)
    original = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=base_start,
        end_time=base_start + timedelta(minutes=30),
        status='booked',
    )
    appointment_db.add(original)
    appointment_db.commit()
    appointment_db.refresh(original)

    before = get_booked_slot_starts(
        now=base_start - timedelta(hours=1),
        range_end=base_start + timedelta(days=1),
        db=appointment_db,
    )
    assert base_start in before

    new_start = base_start + timedelta(hours=1)
    payload = availability_routes.RescheduleAppointmentRequest(
        student_email='student@example.edu',
        start_time=new_start,
    )
    reschedule_appointment(appointment_id=original.id, data=payload, db=appointment_db)

    after = get_booked_slot_starts(
        now=base_start - timedelta(hours=1),
        range_end=base_start + timedelta(days=1),
        db=appointment_db,
    )

    assert base_start not in after
    assert base_start + timedelta(minutes=15) not in after
    assert new_start in after
    assert new_start + timedelta(minutes=15) in after


def test_reschedule_appointment_returns_not_found_when_missing(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    payload = availability_routes.RescheduleAppointmentRequest(
        student_email='student@example.edu',
        start_time=_next_weekday_from_now(hour=10, minute=0),
    )

    with pytest.raises(HTTPException) as exception_info:
        reschedule_appointment(appointment_id=999, data=payload, db=appointment_db)

    assert exception_info.value.status_code == 404
    assert exception_info.value.detail == 'Appointment not found.'


def test_reschedule_appointment_rejects_non_owner(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    base_start = _next_weekday_from_now(hour=10, minute=0)
    original = Appointment(
        student_email='owner@example.edu',
        appointment_type='testing',
        start_time=base_start,
        end_time=base_start + timedelta(minutes=30),
        status='booked',
    )
    appointment_db.add(original)
    appointment_db.commit()
    appointment_db.refresh(original)

    payload = availability_routes.RescheduleAppointmentRequest(
        student_email='student@example.edu',
        start_time=base_start + timedelta(hours=1),
    )

    with pytest.raises(HTTPException) as exception_info:
        reschedule_appointment(appointment_id=original.id, data=payload, db=appointment_db)

    assert exception_info.value.status_code == 403
    assert exception_info.value.detail == 'You can only reschedule your own appointments.'


def test_cancel_my_appointment_normalizes_student_email_before_owner_check(
    appointment_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    appointment = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=_next_weekday_from_now(hour=11, minute=0),
        end_time=_next_weekday_from_now(hour=11, minute=30),
        status='booked',
    )
    appointment_db.add(appointment)
    appointment_db.commit()
    appointment_db.refresh(appointment)

    cancel_my_appointment(
        appointment_id=appointment.id,
        student_email=' STUDENT@EXAMPLE.EDU ',
        db=appointment_db,
    )

    deleted = appointment_db.query(Appointment).filter(Appointment.id == appointment.id).first()
    assert deleted is None


def test_reschedule_appointment_rejects_past_appointment(appointment_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('backend.routes.availability_routes.ensure_database_ready', lambda: None)

    original = Appointment(
        student_email='student@example.edu',
        appointment_type='testing',
        start_time=datetime.now() - timedelta(hours=2),
        end_time=datetime.now() - timedelta(hours=1, minutes=30),
        status='booked',
    )
    appointment_db.add(original)
    appointment_db.commit()
    appointment_db.refresh(original)

    payload = availability_routes.RescheduleAppointmentRequest(
        student_email='student@example.edu',
        start_time=datetime.now() + timedelta(hours=2),
    )

    with pytest.raises(HTTPException) as exception_info:
        reschedule_appointment(appointment_id=original.id, data=payload, db=appointment_db)

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == 'Only upcoming appointments can be rescheduled.'
