"""Tests for Task and Attempt ORM row mapping without a database Session."""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from apiguard.infrastructure.persistence.mappers import (
    apply_attempt_state_to_row,
    apply_task_state_to_row,
    attempt_from_row,
    attempt_to_row,
    task_from_row,
    task_to_row,
)
from apiguard.shared.enums import (
    ValidationAttemptStatus,
    ValidationConclusion,
    VerificationTaskStatus,
    VerificationTaskType,
)
from apiguard.shared.errors import DomainError, IllegalStateTransitionError
from apiguard.shared.ids import (
    EvaluationResultId,
    EvidenceBundleId,
    ExecutionIntentId,
    OpenAPIContextSnapshotId,
    ValidationAttemptId,
    ValidationPlanId,
    VerificationTaskId,
)
from apiguard.tasking.models import ValidationAttempt, VerificationTask

CREATED = datetime(2026, 8, 3, 1, 27, tzinfo=UTC)


def identifier[IdT: str](factory: Callable[[str], IdT]) -> IdT:
    return factory(str(uuid4()))


def task(
    status: VerificationTaskStatus = VerificationTaskStatus.DRAFT,
) -> VerificationTask:
    result = VerificationTask(
        task_id=identifier(VerificationTaskId),
        task_type=VerificationTaskType.BUSINESS_RULE,
        verification_objective="objective",
        created_at=CREATED,
    )
    if status in (VerificationTaskStatus.READY, VerificationTaskStatus.CANCELLED):
        result.start_preparation(CREATED + timedelta(seconds=1))
        result.complete_preparation(CREATED + timedelta(seconds=2))
        result.confirm_plan(
            identifier(ValidationPlanId), CREATED + timedelta(seconds=3)
        )
    if status is VerificationTaskStatus.CANCELLED:
        result.cancel("cancelled", CREATED + timedelta(seconds=4))
    return result


def attempt(
    completed: bool = False, sends: int = 0, rerun: bool = False
) -> ValidationAttempt:
    result = ValidationAttempt(
        attempt_id=identifier(ValidationAttemptId),
        task_id=identifier(VerificationTaskId),
        attempt_no=1,
        plan_id=identifier(ValidationPlanId),
        openapi_snapshot_id=identifier(OpenAPIContextSnapshotId),
        execution_intent_id=identifier(ExecutionIntentId),
        is_rerun=rerun,
        previous_attempt_id=identifier(ValidationAttemptId) if rerun else None,
        created_at=CREATED,
        started_at=CREATED + timedelta(seconds=1),
    )
    for _ in range(sends):
        result.record_http_send()
    if completed:
        result.complete(
            identifier(EvaluationResultId),
            identifier(EvidenceBundleId),
            ValidationConclusion.PASSED,
            CREATED + timedelta(seconds=2),
        )
    return result


@pytest.mark.parametrize(
    "status",
    [
        VerificationTaskStatus.DRAFT,
        VerificationTaskStatus.READY,
        VerificationTaskStatus.CANCELLED,
    ],
)
def test_task_round_trip_preserves_domain_state(status: VerificationTaskStatus) -> None:
    original = task(status)

    restored = task_from_row(task_to_row(original))

    assert restored.status is original.status
    assert restored.current_confirmed_plan_id == original.current_confirmed_plan_id
    if status is VerificationTaskStatus.READY:
        restored.restart_preparation(CREATED + timedelta(seconds=5))
        assert restored.status is VerificationTaskStatus.PREPARING
    if status is VerificationTaskStatus.CANCELLED:
        with pytest.raises(IllegalStateTransitionError):
            restored.start_preparation(CREATED + timedelta(seconds=5))


def test_task_state_update_preserves_future_row_inputs() -> None:
    original = task()
    row = task_to_row(original)
    assert row.original_rule_text is None
    assert row.target_base_url is None
    assert row.test_data_json is None
    row.original_rule_text = "future"
    row.target_base_url = "https://example.test"
    row.test_data_json = '{"future": true}'
    original.start_preparation(CREATED + timedelta(seconds=1))

    apply_task_state_to_row(original, row)

    assert row.status == "PREPARING"
    assert (row.original_rule_text, row.target_base_url, row.test_data_json) == (
        "future",
        "https://example.test",
        '{"future": true}',
    )


@pytest.mark.parametrize("sends", [0, 2, 3])
def test_executing_attempt_round_trips_with_send_count(sends: int) -> None:
    restored = attempt_from_row(attempt_to_row(attempt(sends=sends)))

    assert restored.status is ValidationAttemptStatus.EXECUTING
    assert restored.actual_send_count == sends
    if sends == 2:
        restored.record_http_send()
        assert restored.actual_send_count == 3


def test_completed_and_rerun_attempt_round_trip() -> None:
    restored = attempt_from_row(attempt_to_row(attempt(completed=True, rerun=True)))

    assert restored.status is ValidationAttemptStatus.COMPLETED
    assert restored.is_rerun
    with pytest.raises(IllegalStateTransitionError):
        restored.record_http_send()


def test_attempt_state_update_does_not_replace_fixed_bindings() -> None:
    original = attempt(sends=1)
    row = attempt_to_row(original)
    fixed = (
        row.attempt_id,
        row.task_id,
        row.plan_id,
        row.openapi_snapshot_id,
        row.execution_intent_id,
    )
    original.record_http_send()

    apply_attempt_state_to_row(original, row)

    assert (
        row.attempt_id,
        row.task_id,
        row.plan_id,
        row.openapi_snapshot_id,
        row.execution_intent_id,
    ) == fixed
    assert row.actual_send_count == 2


def test_invalid_row_values_are_rejected_before_or_by_domain_reconstitution() -> None:
    row = attempt_to_row(attempt())
    row.attempt_id = "not-a-uuid"
    with pytest.raises(ValueError):
        attempt_from_row(row)
    row = attempt_to_row(attempt())
    row.actual_send_count = 4
    with pytest.raises(DomainError):
        attempt_from_row(row)


def test_only_mapper_production_code_calls_reconstitute() -> None:
    source_root = Path("src")
    callers = [
        path
        for path in source_root.rglob("*.py")
        if re.search(r"(?<!def )_reconstitute\(", path.read_text(encoding="utf-8"))
    ]

    assert callers == [
        source_root / "apiguard" / "infrastructure" / "persistence" / "mappers.py"
    ]
