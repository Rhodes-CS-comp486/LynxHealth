"""Main FastAPI application entry point."""

from fastapi import FastAPI
from backend.database import engine
from backend.models import user, appointment, availability
from backend.routes import auth_routes

app = FastAPI()

user.Base.metadata.create_all(bind=engine)
appointment.Base.metadata.create_all(bind=engine)
availability.Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    """Return a basic health check payload."""
    return {"status": "Health Center API Running"}

app.include_router(auth_routes.router, prefix="/auth")
