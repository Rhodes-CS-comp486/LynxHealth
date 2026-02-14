import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres@localhost:5432/postgres')

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
