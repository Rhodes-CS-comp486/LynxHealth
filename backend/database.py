import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

def resolve_database_url() -> str:
    raw_url = os.getenv('DATABASE_URL', '').strip()

    if raw_url.startswith('jdbc:'):
        raw_url = raw_url.replace('jdbc:', '', 1)

    has_placeholder_credentials = '<user>' in raw_url or '<password>' in raw_url
    if not raw_url or has_placeholder_credentials:
        # Default without explicit username/password so local Postgres can use
        # the current OS account in common developer setups.
        return 'postgresql://localhost:5432/postgres'

    return raw_url


DATABASE_URL = resolve_database_url()

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def ensure_availability_schema() -> None:
    inspector = inspect(engine)

    if 'availability' not in inspector.get_table_names():
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
