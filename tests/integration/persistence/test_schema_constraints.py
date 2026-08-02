"""Database-enforced constraints for the frozen initial SQLite schema."""

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from apiguard.infrastructure.persistence.database import create_sqlite_engine

TIME = "2026-08-03T01:27:00.000000Z"
SHA = "a" * 64


@pytest.fixture
def engine(migrated_database: Path) -> Iterator[Engine]:
    engine = create_sqlite_engine(migrated_database)
    yield engine
    engine.dispose()


def _execute(
    connection: Connection, statement: str, values: Mapping[str, object]
) -> None:
    connection.execute(text(statement), values)
    connection.commit()


def _task(connection: Connection, task_id: str) -> None:
    _execute(
        connection,
        """
        INSERT INTO verification_tasks
        (task_id, task_type, verification_objective, status, created_at, updated_at)
        VALUES (:task_id, 'BUSINESS_RULE', 'objective', 'DRAFT', :time, :time)
        """,
        {"task_id": task_id, "time": TIME},
    )


def _plan_graph(connection: Connection, task_id: str, suffix: str) -> tuple[str, str]:
    snapshot_id = f"snapshot-{suffix}"
    model_call_id = f"model-{suffix}"
    rule_id = f"rule-{suffix}"
    plan_id = f"plan-{suffix}"
    _execute(
        connection,
        """
        INSERT INTO openapi_snapshots
        (openapi_snapshot_id, task_id, version_no, source_kind, source_display_value,
         openapi_version, raw_document, raw_size_bytes, content_sha256,
         normalized_context_json, diagnostics_json, created_at)
        VALUES (:snapshot_id, :task_id, 1, 'URL', 'source', '3.1.0', '{}', 2, :sha,
                '{}', '[]', :time)
        """,
        {"snapshot_id": snapshot_id, "task_id": task_id, "sha": SHA, "time": TIME},
    )
    _execute(
        connection,
        """
        INSERT INTO model_call_records
        (model_call_id, task_id, openapi_snapshot_id, preparation_run_id, call_sequence,
         call_kind, provider_name, model_name, prompt_version, status, started_at)
        VALUES (:model_call_id, :task_id, :snapshot_id, :run_id, 1, 'PRIMARY',
                'provider', 'model', 'v1', 'SUCCEEDED', :time)
        """,
        {
            "model_call_id": model_call_id,
            "task_id": task_id,
            "snapshot_id": snapshot_id,
            "run_id": f"run-{suffix}",
            "time": TIME,
        },
    )
    _execute(
        connection,
        """
        INSERT INTO normalized_rules
        (normalized_rule_id, task_id, openapi_snapshot_id, model_call_id, version_no,
         original_rule_text, normalized_rule_json, content_sha256, created_at)
        VALUES (:rule_id, :task_id, :snapshot_id, :model_call_id, 1, 'rule', '{}', :sha,
                :time)
        """,
        {
            "rule_id": rule_id,
            "task_id": task_id,
            "snapshot_id": snapshot_id,
            "model_call_id": model_call_id,
            "sha": SHA,
            "time": TIME,
        },
    )
    _execute(
        connection,
        """
        INSERT INTO validation_plan_snapshots
        (plan_id, task_id, normalized_rule_id, openapi_snapshot_id, version_no, stage,
         plan_json, content_sha256, created_at)
        VALUES (:plan_id, :task_id, :rule_id, :snapshot_id, 1, 'CONFIRMED', '{}', :sha,
                :time)
        """,
        {
            "plan_id": plan_id,
            "task_id": task_id,
            "rule_id": rule_id,
            "snapshot_id": snapshot_id,
            "sha": SHA,
            "time": TIME,
        },
    )
    return plan_id, snapshot_id


def _attempt(
    connection: Connection,
    *,
    attempt_id: str,
    task_id: str,
    plan_id: str,
    snapshot_id: str,
    attempt_no: int,
    intent_id: str,
    status: str = "EXECUTING",
) -> None:
    _execute(
        connection,
        """
        INSERT INTO validation_attempts
        (attempt_id, task_id, attempt_no, plan_id, openapi_snapshot_id, status,
         execution_intent_id, is_rerun, created_at, started_at, actual_send_count)
        VALUES (:attempt_id, :task_id, :attempt_no, :plan_id, :snapshot_id, :status,
                :intent_id, 0, :time, :time, 0)
        """,
        {
            "attempt_id": attempt_id,
            "task_id": task_id,
            "attempt_no": attempt_no,
            "plan_id": plan_id,
            "snapshot_id": snapshot_id,
            "status": status,
            "intent_id": intent_id,
            "time": TIME,
        },
    )


def test_foreign_key_rejects_child_without_task(engine: Engine) -> None:
    with engine.connect() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO openapi_snapshots "
                "(openapi_snapshot_id, task_id, version_no, source_kind, "
                "source_display_value, openapi_version, raw_document, raw_size_bytes, "
                "content_sha256, normalized_context_json, diagnostics_json, created_at) "
                "VALUES ('snapshot', 'missing-task', 1, 'URL', 'source', '3.1.0', '{}', "
                "2, :sha, '{}', '[]', :time)"
            ),
            {"sha": SHA, "time": TIME},
        )


def test_attempt_partial_unique_index_and_execution_intent_constraints(
    engine: Engine,
) -> None:
    with engine.connect() as connection:
        _task(connection, "task-a")
        plan_id, snapshot_id = _plan_graph(connection, "task-a", "a")
        _attempt(
            connection,
            attempt_id="attempt-a1",
            task_id="task-a",
            plan_id=plan_id,
            snapshot_id=snapshot_id,
            attempt_no=1,
            intent_id="intent-a1",
        )
        with pytest.raises(IntegrityError):
            _attempt(
                connection,
                attempt_id="attempt-a2",
                task_id="task-a",
                plan_id=plan_id,
                snapshot_id=snapshot_id,
                attempt_no=2,
                intent_id="intent-a2",
            )
        connection.rollback()
        connection.execute(
            text(
                "UPDATE validation_attempts SET status = 'COMPLETED' WHERE attempt_id = 'attempt-a1'"
            )
        )
        connection.commit()
        _attempt(
            connection,
            attempt_id="attempt-a2",
            task_id="task-a",
            plan_id=plan_id,
            snapshot_id=snapshot_id,
            attempt_no=2,
            intent_id="intent-a2",
        )
        with pytest.raises(IntegrityError):
            _attempt(
                connection,
                attempt_id="attempt-a3",
                task_id="task-a",
                plan_id=plan_id,
                snapshot_id=snapshot_id,
                attempt_no=3,
                intent_id="intent-a2",
            )
        connection.rollback()
        _task(connection, "task-b")
        plan_b, snapshot_b = _plan_graph(connection, "task-b", "b")
        _attempt(
            connection,
            attempt_id="attempt-b1",
            task_id="task-b",
            plan_id=plan_b,
            snapshot_id=snapshot_b,
            attempt_no=1,
            intent_id="intent-a2",
        )


def test_attempt_composite_foreign_key_rejects_mismatched_plan_and_snapshot(
    engine: Engine,
) -> None:
    with engine.connect() as connection:
        _task(connection, "task-a")
        _task(connection, "task-b")
        plan_a, snapshot_a = _plan_graph(connection, "task-a", "a")
        _, snapshot_b = _plan_graph(connection, "task-b", "b")
        with pytest.raises(IntegrityError):
            _attempt(
                connection,
                attempt_id="bad-task",
                task_id="task-b",
                plan_id=plan_a,
                snapshot_id=snapshot_a,
                attempt_no=1,
                intent_id="intent-bad-task",
            )
        connection.rollback()
        with pytest.raises(IntegrityError):
            _attempt(
                connection,
                attempt_id="bad-snapshot",
                task_id="task-a",
                plan_id=plan_a,
                snapshot_id=snapshot_b,
                attempt_no=1,
                intent_id="intent-bad-snapshot",
            )


def test_evaluation_bundle_step_and_send_uniqueness(engine: Engine) -> None:
    with engine.connect() as connection:
        _task(connection, "task-a")
        plan_id, snapshot_id = _plan_graph(connection, "task-a", "a")
        _attempt(
            connection,
            attempt_id="attempt-a",
            task_id="task-a",
            plan_id=plan_id,
            snapshot_id=snapshot_id,
            attempt_no=1,
            intent_id="intent-a",
        )
        values = {
            "attempt_id": "attempt-a",
            "plan_id": plan_id,
            "snapshot_id": snapshot_id,
            "sha": SHA,
            "time": TIME,
        }
        _execute(
            connection,
            "INSERT INTO evaluation_results (evaluation_result_id, attempt_id, plan_id, openapi_snapshot_id, evaluation_input_sha256, assertions_json, required_steps_complete, preconditions_proven, critical_evidence_missing, attribution_ambiguous, conclusion, decision_code, decision_detail_json, created_at) VALUES ('evaluation-a', :attempt_id, :plan_id, :snapshot_id, :sha, '[]', 1, 1, 0, 0, 'PASSED', 'OK', '{}', :time)",
            values,
        )
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO evaluation_results (evaluation_result_id, attempt_id, plan_id, openapi_snapshot_id, evaluation_input_sha256, assertions_json, required_steps_complete, preconditions_proven, critical_evidence_missing, attribution_ambiguous, conclusion, decision_code, decision_detail_json, created_at) VALUES ('evaluation-b', :attempt_id, :plan_id, :snapshot_id, :sha, '[]', 1, 1, 0, 0, 'PASSED', 'OK', '{}', :time)",
                values,
            )
        connection.rollback()
        _execute(
            connection,
            "INSERT INTO evidence_bundles (evidence_bundle_id, attempt_id, task_id, plan_id, openapi_snapshot_id, evaluation_result_id, bundle_format_version, manifest_json, manifest_sha256, sealed_at) VALUES ('bundle-a', 'attempt-a', 'task-a', :plan_id, :snapshot_id, 'evaluation-a', 'v1', '{}', :sha, :time)",
            {"plan_id": plan_id, "snapshot_id": snapshot_id, "sha": SHA, "time": TIME},
        )
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO evidence_bundles (evidence_bundle_id, attempt_id, task_id, plan_id, openapi_snapshot_id, evaluation_result_id, bundle_format_version, manifest_json, manifest_sha256, sealed_at) VALUES ('bundle-b', 'attempt-a', 'task-a', :plan_id, :snapshot_id, 'evaluation-a', 'v1', '{}', :sha, :time)",
                {
                    "plan_id": plan_id,
                    "snapshot_id": snapshot_id,
                    "sha": SHA,
                    "time": TIME,
                },
            )
        connection.rollback()
        _execute(
            connection,
            "INSERT INTO step_execution_records (step_record_id, attempt_id, plan_step_id, step_index, status, send_count) VALUES ('step-a', 'attempt-a', 'plan-step-a', 1, 'PENDING', 0)",
            {},
        )
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO step_execution_records (step_record_id, attempt_id, plan_step_id, step_index, status, send_count) VALUES ('step-b', 'attempt-a', 'plan-step-a', 1, 'PENDING', 0)",
                {},
            )
        connection.rollback()
        _execute(
            connection,
            "INSERT INTO http_send_records (send_record_id, attempt_id, step_record_id, global_send_no, send_no_in_step, is_retry, status, method, sanitized_url, query_params_json, request_headers_json, request_body_size_bytes, dispatched_at, response_truncated) VALUES ('send-a', 'attempt-a', 'step-a', 1, 1, 0, 'DISPATCHED', 'GET', 'http://example.test', '{}', '{}', 0, :time, 0)",
            {"time": TIME},
        )
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO http_send_records (send_record_id, attempt_id, step_record_id, global_send_no, send_no_in_step, is_retry, status, method, sanitized_url, query_params_json, request_headers_json, request_body_size_bytes, dispatched_at, response_truncated) VALUES ('send-b', 'attempt-a', 'step-a', 1, 1, 0, 'DISPATCHED', 'GET', 'http://example.test', '{}', '{}', 0, :time, 0)",
                {"time": TIME},
            )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO verification_tasks (task_id, task_type, verification_objective, status, created_at, updated_at) VALUES ('bad-task', 'BUSINESS_RULE', 'objective', 'BAD', :time, :time)",
        "INSERT INTO validation_attempts (attempt_id, task_id, attempt_no, plan_id, openapi_snapshot_id, status, execution_intent_id, is_rerun, created_at, started_at, actual_send_count) VALUES ('bad-attempt', 'task-a', 2, :plan_id, :snapshot_id, 'BAD', 'intent-bad', 0, :time, :time, 0)",
    ],
)
def test_enum_checks_reject_invalid_task_and_attempt_statuses(
    engine: Engine, statement: str
) -> None:
    with engine.connect() as connection:
        _task(connection, "task-a")
        plan_id, snapshot_id = _plan_graph(connection, "task-a", "a")
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                statement,
                {"plan_id": plan_id, "snapshot_id": snapshot_id, "time": TIME},
            )


def test_enum_checks_reject_invalid_conclusion_send_status_and_method(
    engine: Engine,
) -> None:
    with engine.connect() as connection:
        _task(connection, "task-a")
        plan_id, snapshot_id = _plan_graph(connection, "task-a", "a")
        _attempt(
            connection,
            attempt_id="attempt-a",
            task_id="task-a",
            plan_id=plan_id,
            snapshot_id=snapshot_id,
            attempt_no=1,
            intent_id="intent-a",
        )
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO evaluation_results (evaluation_result_id, attempt_id, "
                "plan_id, openapi_snapshot_id, evaluation_input_sha256, "
                "assertions_json, required_steps_complete, preconditions_proven, "
                "critical_evidence_missing, attribution_ambiguous, conclusion, "
                "decision_code, decision_detail_json, created_at) "
                "VALUES ('bad-evaluation', 'attempt-a', :plan_id, :snapshot_id, :sha, "
                "'[]', 1, 1, 0, 0, 'BAD', 'OK', '{}', :time)",
                {
                    "plan_id": plan_id,
                    "snapshot_id": snapshot_id,
                    "sha": SHA,
                    "time": TIME,
                },
            )
        connection.rollback()
        _execute(
            connection,
            "INSERT INTO step_execution_records "
            "(step_record_id, attempt_id, plan_step_id, step_index, status, send_count) "
            "VALUES ('step-a', 'attempt-a', 'plan-step-a', 1, 'PENDING', 0)",
            {},
        )
        for record_id, status, method in (
            ("bad-method", "DISPATCHED", "TRACE"),
            ("bad-status", "BAD", "GET"),
        ):
            with pytest.raises(IntegrityError):
                _execute(
                    connection,
                    "INSERT INTO http_send_records "
                    "(send_record_id, attempt_id, step_record_id, global_send_no, "
                    "send_no_in_step, is_retry, status, method, sanitized_url, "
                    "query_params_json, request_headers_json, request_body_size_bytes, "
                    "dispatched_at, response_truncated) "
                    "VALUES (:record_id, 'attempt-a', 'step-a', 1, 1, 0, :status, "
                    ":method, 'http://example.test', '{}', '{}', 0, :time, 0)",
                    {
                        "record_id": record_id,
                        "status": status,
                        "method": method,
                        "time": TIME,
                    },
                )
            connection.rollback()


def test_enum_boolean_and_sha256_checks(engine: Engine) -> None:
    with engine.connect() as connection:
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO verification_tasks (task_id, task_type, verification_objective, non_production_confirmed, status, created_at, updated_at) VALUES ('bad-bool', 'BUSINESS_RULE', 'objective', 2, 'DRAFT', :time, :time)",
                {"time": TIME},
            )
        connection.rollback()
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO openapi_snapshots "
                "(openapi_snapshot_id, task_id, version_no, source_kind, "
                "source_display_value, openapi_version, raw_document, raw_size_bytes, "
                "content_sha256, normalized_context_json, diagnostics_json, created_at) "
                "VALUES ('short-sha', 'task-a', 1, 'URL', 'source', '3.1.0', '{}', 2, "
                ":sha, '{}', '[]', :time)",
                {"sha": SHA[:-1], "time": TIME},
            )
        connection.rollback()
        _task(connection, "task-a")
        with pytest.raises(IntegrityError):
            _execute(
                connection,
                "INSERT INTO openapi_snapshots (openapi_snapshot_id, task_id, version_no, source_kind, source_display_value, openapi_version, raw_document, raw_size_bytes, content_sha256, normalized_context_json, diagnostics_json, created_at) VALUES ('bad-sha', 'task-a', 1, 'URL', 'source', '3.1.0', '{}', 2, 'A' || :sha, '{}', '[]', :time)",
                {"sha": SHA[:-1], "time": TIME},
            )
        connection.rollback()
        _execute(
            connection,
            "INSERT INTO openapi_snapshots (openapi_snapshot_id, task_id, version_no, source_kind, source_display_value, openapi_version, raw_document, raw_size_bytes, content_sha256, normalized_context_json, diagnostics_json, created_at) VALUES ('good-sha', 'task-a', 1, 'URL', 'source', '3.1.0', '{}', 2, :sha, '{}', '[]', :time)",
            {"sha": SHA, "time": TIME},
        )
