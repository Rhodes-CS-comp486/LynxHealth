from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import engine, ensure_availability_schema
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

user.Base.metadata.create_all(bind=engine)
appointment.Base.metadata.create_all(bind=engine)
availability.Base.metadata.create_all(bind=engine)
ensure_availability_schema()


@app.get('/')
def root():
    return {'status': 'Health Center API Running'}


app.include_router(auth_routes.router, prefix='/auth')
app.include_router(availability_routes.router, prefix='/availability')
