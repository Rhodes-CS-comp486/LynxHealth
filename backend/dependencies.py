def get_db():
"""
Shared FastAPI dependency providers for the LynxHealth backend.

This module contains dependency functions for use with FastAPI's Depends system.
"""

from backend.database import SessionLocal

def get_db():
    """
    Yield a SQLAlchemy database session and close it when the request is done.

    Intended for use as a FastAPI dependency via ``Depends(get_db)``.
    The session is always closed in the ``finally`` block, whether the
    request succeeds or raises an exception.

    Yields:
        Session: An active SQLAlchemy ORM session bound to the configured database.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()