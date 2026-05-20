"""Database connection setup."""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "onchain_monitor.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode for concurrent reads (dashboard) + writes (collector)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionFactory = sessionmaker(bind=engine)
ScopedSession = scoped_session(SessionFactory)


def get_session():
    return ScopedSession()
