"""
Shared FastAPI dependency providers for the LynxHealth backend.

"""

from backend.database import SessionLocal


def get_db():
    """
    Yield a SQLAlchemy database session and close it when the request is done.

    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
