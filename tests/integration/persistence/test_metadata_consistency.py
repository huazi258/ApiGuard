"""Tests that ORM metadata mirrors the frozen initial Alembic migration."""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex

from apiguard.infrastructure.persistence.orm import Base, ValidationAttemptRow


def test_partial_executing_attempt_index_compiles_for_sqlite() -> None:
    index = next(
        index
        for index in Base.metadata.tables["validation_attempts"].indexes
        if index.name == "uq_validation_attempt_one_executing_per_task"
    )
    compiled = str(CreateIndex(index).compile(dialect=sqlite.dialect()))

    assert "WHERE status = 'EXECUTING'" in compiled


def test_explicit_metadata_constraint_names_match_initial_migration() -> None:
    expected_unique_names = {
        "openapi_snapshots": {
            "uq_openapi_snapshots_task_version",
            "uq_openapi_snapshots_task_snapshot",
        },
        "model_call_records": {"uq_model_call_records_run_sequence"},
        "normalized_rules": {"uq_normalized_rules_task_version"},
        "validation_plan_snapshots": {
            "uq_validation_plan_snapshots_task_version",
            "uq_validation_plan_snapshots_task_plan",
            "uq_validation_plan_snapshots_task_plan_snapshot",
        },
        "validation_attempts": {
            "uq_validation_attempts_task_attempt_no",
            "uq_validation_attempts_task_execution_intent",
        },
        "step_execution_records": {
            "uq_step_execution_records_attempt_step_index",
            "uq_step_execution_records_attempt_plan_step",
        },
        "http_send_records": {
            "uq_http_send_records_step_send_no",
            "uq_http_send_records_attempt_global_send_no",
        },
        "derived_reports": {"uq_derived_reports_bundle_version"},
    }

    for table_name, expected_names in expected_unique_names.items():
        table = Base.metadata.tables[table_name]
        actual_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert expected_names <= actual_names

    task_foreign_keys = {
        constraint.name
        for constraint in Base.metadata.tables["verification_tasks"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    attempt_foreign_keys = {
        constraint.name
        for constraint in Base.metadata.tables["validation_attempts"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert "fk_verification_tasks_current_confirmed_plan" in task_foreign_keys
    assert "fk_validation_attempts_plan_snapshot" in attempt_foreign_keys


def test_metadata_server_defaults_match_initial_migration() -> None:
    columns = (
        Base.metadata.tables["step_execution_records"].c.send_count,
        Base.metadata.tables["http_send_records"].c.is_retry,
        Base.metadata.tables["http_send_records"].c.response_truncated,
    )

    assert [str(column.server_default) for column in columns] == [
        "DefaultClause('0', for_update=False)",
        "DefaultClause('0', for_update=False)",
        "DefaultClause('0', for_update=False)",
    ]


def test_metadata_exposes_all_frozen_business_tables() -> None:
    assert ValidationAttemptRow.__table__ is Base.metadata.tables["validation_attempts"]
    assert len(Base.metadata.tables) == 11
