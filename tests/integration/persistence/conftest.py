"""Fixtures that migrate isolated file-backed SQLite databases."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def upgrade_database(database_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Upgrade one explicit test database without using ORM create_all."""

    monkeypatch.setenv("APIGUARD_DATABASE_PATH", str(database_path))
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def migrated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a database created only by the Alembic initial migration."""

    database_path = tmp_path / "apiguard.db"
    upgrade_database(database_path, monkeypatch)
    return database_path
