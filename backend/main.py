import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.database import engine, ensure_availability_schema, ensure_appointment_schema
from backend.models import user, appointment, availability
from backend.routes import auth_routes, availability_routes

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:4200'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
) 

logger = logging.getLogger(__name__)


@app.on_event('startup')
def initialize_database() -> None:
    try:
        user.Base.metadata.create_all(bind=engine)
        appointment.Base.metadata.create_all(bind=engine)
        availability.Base.metadata.create_all(bind=engine)
        ensure_availability_schema()
        ensure_appointment_schema()
    except SQLAlchemyError:
        logger.exception('Database initialization failed. Check DATABASE_URL and Postgres credentials.')


@app.get('/')
def root():
    return {'status': 'Health Center API Running'}


app.include_router(auth_routes.router, prefix='/auth')
app.include_router(availability_routes.router, prefix='/availability')
