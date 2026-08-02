"""Tests for replaying the single initial Alembic migration."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.integration.persistence.conftest import upgrade_database

BUSINESS_TABLES = {
    "verification_tasks",
    "openapi_snapshots",
    "model_call_records",
    "normalized_rules",
    "validation_plan_snapshots",
    "validation_attempts",
    "step_execution_records",
    "http_send_records",
    "evaluation_results",
    "evidence_bundles",
    "derived_reports",
}


def test_empty_file_upgrades_to_exact_initial_schema(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_path = tmp_path / "initial.db"
    assert not database_path.exists()

    upgrade_database(database_path, monkeypatch)  # type: ignore[arg-type]

    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    try:
        assert set(inspect(engine).get_table_names()) == BUSINESS_TABLES | {
            "alembic_version"
        }
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "20260803_01"
            )
    finally:
        engine.dispose()


def test_initial_migration_can_upgrade_downgrade_and_upgrade_again(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_path = tmp_path / "replay.db"
    upgrade_database(database_path, monkeypatch)  # type: ignore[arg-type]

    command.downgrade(Config("alembic.ini"), "base")

    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    try:
        assert inspect(engine).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()

    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    try:
        assert set(inspect(engine).get_table_names()) == BUSINESS_TABLES | {
            "alembic_version"
        }
    finally:
        engine.dispose()
