import os
from dotenv import load_dotenv
from threading import Lock

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

_schema_lock = Lock()
_availability_schema_checked = False
_appointment_schema_checked = False
_appointment_type_option_schema_checked = False
_clinic_hours_schema_checked = False
_clinic_holidays_schema_checked = False


def ensure_availability_schema() -> None:
    global _availability_schema_checked

    if _availability_schema_checked:
        return

    with _schema_lock:
        if _availability_schema_checked:
            return

        inspector = inspect(engine)

        if 'availability' not in inspector.get_table_names():
            _availability_schema_checked = True
            return

        existing_columns = {column['name'] for column in inspector.get_columns('availability')}
        migration_steps = [
            ('date', 'ALTER TABLE availability ADD COLUMN date DATE'),
            ('time', 'ALTER TABLE availability ADD COLUMN time TIME'),
            ('duration_minutes', 'ALTER TABLE availability ADD COLUMN duration_minutes INTEGER'),
            ('appointment_type', 'ALTER TABLE availability ADD COLUMN appointment_type VARCHAR'),
        ]

        with engine.begin() as connection:
            for column_name, statement in migration_steps:
                if column_name not in existing_columns:
                    connection.execute(text(statement))
            connection.execute(
                text('CREATE INDEX IF NOT EXISTS idx_availability_time_range ON availability(start_time, end_time)')
            )
            connection.execute(
                text('CREATE INDEX IF NOT EXISTS idx_availability_type_start ON availability(appointment_type, start_time)')
            )
            connection.execute(
                text('CREATE INDEX IF NOT EXISTS idx_availability_booked_start ON availability(is_booked, start_time)')
            )

        _availability_schema_checked = True


def ensure_appointment_schema() -> None:
    global _appointment_schema_checked

    if _appointment_schema_checked:
        return

    with _schema_lock:
        if _appointment_schema_checked:
            return

        inspector = inspect(engine)

        if 'appointments' not in inspector.get_table_names():
            _appointment_schema_checked = True
            return

        existing_columns = {column['name'] for column in inspector.get_columns('appointments')}
        migration_steps = [
            ('student_email', 'ALTER TABLE appointments ADD COLUMN student_email VARCHAR'),
            ('appointment_type', 'ALTER TABLE appointments ADD COLUMN appointment_type VARCHAR'),
            ('notes', 'ALTER TABLE appointments ADD COLUMN notes VARCHAR'),
        ]

        with engine.begin() as connection:
            for column_name, statement in migration_steps:
                if column_name not in existing_columns:
                    connection.execute(text(statement))
            connection.execute(
                text('CREATE INDEX IF NOT EXISTS idx_appointments_time_range ON appointments(start_time, end_time)')
            )
            connection.execute(
                text('CREATE INDEX IF NOT EXISTS idx_appointments_type_start ON appointments(appointment_type, start_time)')
            )

        _appointment_schema_checked = True


def ensure_appointment_type_option_schema() -> None:
    global _appointment_type_option_schema_checked

    if _appointment_type_option_schema_checked:
        return

    with _schema_lock:
        if _appointment_type_option_schema_checked:
            return

        inspector = inspect(engine)

        if 'appointment_type_options' not in inspector.get_table_names():
            _appointment_type_option_schema_checked = True
            return

        existing_columns = {column['name'] for column in inspector.get_columns('appointment_type_options')}
        migration_steps = [
            ('appointment_type', 'ALTER TABLE appointment_type_options ADD COLUMN appointment_type VARCHAR'),
            ('duration_minutes', 'ALTER TABLE appointment_type_options ADD COLUMN duration_minutes INTEGER'),
        ]

        with engine.begin() as connection:
            for column_name, statement in migration_steps:
                if column_name not in existing_columns:
                    connection.execute(text(statement))
            connection.execute(
                text('CREATE UNIQUE INDEX IF NOT EXISTS idx_appointment_type_options_name ON appointment_type_options(appointment_type)')
            )

        _appointment_type_option_schema_checked = True


def ensure_clinic_hours_schema() -> None:
    global _clinic_hours_schema_checked

    if _clinic_hours_schema_checked:
        return

    with _schema_lock:
        if _clinic_hours_schema_checked:
            return

        inspector = inspect(engine)

        if 'clinic_hours' not in inspector.get_table_names():
            _clinic_hours_schema_checked = True
            return

        existing_columns = {column['name'] for column in inspector.get_columns('clinic_hours')}
        migration_steps = [
            ('day_of_week', 'ALTER TABLE clinic_hours ADD COLUMN day_of_week INTEGER'),
            ('is_open', 'ALTER TABLE clinic_hours ADD COLUMN is_open BOOLEAN DEFAULT FALSE'),
            ('open_time', 'ALTER TABLE clinic_hours ADD COLUMN open_time TIME'),
            ('close_time', 'ALTER TABLE clinic_hours ADD COLUMN close_time TIME'),
        ]

        with engine.begin() as connection:
            for column_name, statement in migration_steps:
                if column_name not in existing_columns:
                    connection.execute(text(statement))
            connection.execute(
                text('CREATE UNIQUE INDEX IF NOT EXISTS idx_clinic_hours_day_of_week ON clinic_hours(day_of_week)')
            )

        _clinic_hours_schema_checked = True


def ensure_clinic_holidays_schema() -> None:
    global _clinic_holidays_schema_checked

    if _clinic_holidays_schema_checked:
        return

    with _schema_lock:
        if _clinic_holidays_schema_checked:
            return

        inspector = inspect(engine)

        if 'clinic_holidays' not in inspector.get_table_names():
            _clinic_holidays_schema_checked = True
            return

        existing_columns = {column['name'] for column in inspector.get_columns('clinic_holidays')}
        migration_steps = [
            ('holiday_date', 'ALTER TABLE clinic_holidays ADD COLUMN holiday_date DATE'),
            ('name', 'ALTER TABLE clinic_holidays ADD COLUMN name VARCHAR'),
            ('is_annual', 'ALTER TABLE clinic_holidays ADD COLUMN is_annual BOOLEAN DEFAULT FALSE'),
        ]

        with engine.begin() as connection:
            for column_name, statement in migration_steps:
                if column_name not in existing_columns:
                    connection.execute(text(statement))
            connection.execute(
                text('CREATE UNIQUE INDEX IF NOT EXISTS idx_clinic_holidays_date ON clinic_holidays(holiday_date)')
            )

        _clinic_holidays_schema_checked = True
