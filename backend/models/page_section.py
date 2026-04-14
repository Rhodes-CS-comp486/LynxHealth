"""
SQLAlchemy model for page sections (editable content blocks) in the LynxHealth system.
"""
from sqlalchemy import Column, Integer, String, Text

from backend.database import Base

class PageSection(Base):
    """Represents a content section on a page."""
    __tablename__ = 'page_sections'

    id = Column(Integer, primary_key=True)
    page = Column(String, nullable=False, index=True)
    section_key = Column(String, nullable=False)
    header = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
