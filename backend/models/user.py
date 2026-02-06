"""User model definitions."""

from sqlalchemy import Column, Integer, String
from backend.database import Base


class User(Base):
    """Represents an application user."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)  # student/admin
