"""Auto-create database tables on startup."""

from database.models import Base
from database.connection import engine


def init_database():
    Base.metadata.create_all(engine)
