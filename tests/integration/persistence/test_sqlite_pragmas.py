"""Tests for per-connection SQLite safety pragmas."""

from pathlib import Path

from sqlalchemy import text

from apiguard.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)


def _pragma_values(connection: object) -> tuple[int, str, int, int]:
    return (
        connection.execute(text("PRAGMA foreign_keys")).scalar_one(),  # type: ignore[union-attr]
        connection.execute(text("PRAGMA journal_mode")).scalar_one(),  # type: ignore[union-attr]
        connection.execute(text("PRAGMA synchronous")).scalar_one(),  # type: ignore[union-attr]
        connection.execute(text("PRAGMA busy_timeout")).scalar_one(),  # type: ignore[union-attr]
    )


def test_each_sqlite_connection_uses_frozen_pragmas(migrated_database: Path) -> None:
    engine = create_sqlite_engine(migrated_database)
    try:
        with engine.connect() as first, engine.connect() as second:
            assert _pragma_values(first) == (1, "wal", 1, 5000)
            assert _pragma_values(second) == (1, "wal", 1, 5000)
    finally:
        engine.dispose()


def test_session_factory_creates_independent_synchronous_sessions(
    migrated_database: Path,
) -> None:
    engine = create_sqlite_engine(migrated_database)
    try:
        factory = create_session_factory(engine)
        first = factory()
        second = factory()
        try:
            assert first is not second
            assert not first.autoflush
            assert not first.expire_on_commit
        finally:
            first.close()
            second.close()
    finally:
        engine.dispose()
