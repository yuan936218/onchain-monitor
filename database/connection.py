"""Database connection setup — SQLite with NullPool (no connection pooling).

SQLite connections are lightweight file handles. Pooling adds complexity
without benefit and causes TimeoutError when Streamlit's thread pool and
APScheduler's background threads compete for connections.

NullPool means each session gets a fresh connection, and closing the
session returns it to the OS immediately — no pool to exhaust.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "onchain_monitor.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,  # No pooling — SQLite connections are just files
)


# Enable WAL mode for concurrent reads + writes
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-8000")  # 8 MB page cache
    cursor.close()


SessionFactory = sessionmaker(bind=engine)
ScopedSession = scoped_session(SessionFactory)


def get_session():
    """Get a thread-local session. Call ScopedSession.remove() when done."""
    return ScopedSession()
