"""
SQLAlchemy model for users in the LynxHealth system.
"""
from sqlalchemy import Column, Integer, String
from backend.database import Base


class User(Base):
    """Represents a user (student or admin) in the system."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)  # student/admin