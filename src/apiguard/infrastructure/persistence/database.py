"""Synchronous SQLite engine and session factory construction."""

from pathlib import Path
from sqlite3 import Connection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def sqlite_url_from_path(database_path: Path) -> str:
    """Return a file-based SQLite URL for one explicit database path."""

    return f"sqlite+pysqlite:///{database_path.expanduser().resolve().as_posix()}"


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create a SQLite engine without opening a connection at import time."""

    resolved_path = database_path.expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        sqlite_url_from_path(resolved_path),
        connect_args={"check_same_thread": False},
    )

    def configure_sqlite_connection(dbapi_connection: Connection, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    event.listen(engine, "connect", configure_sqlite_connection)

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create independent synchronous sessions for future units of work."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
