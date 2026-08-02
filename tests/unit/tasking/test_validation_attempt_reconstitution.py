"""Tests for restoring persisted ValidationAttempt state without replaying behavior."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

import apiguard.tasking as tasking
from apiguard.shared.enums import ValidationAttemptStatus, ValidationConclusion
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
from apiguard.tasking.models import ValidationAttempt

CREATED_AT = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
STARTED_AT = CREATED_AT + timedelta(seconds=1)
COMPLETED_AT = STARTED_AT + timedelta(seconds=1)
ATTEMPT_ID = ValidationAttemptId("attempt-1")
TASK_ID = VerificationTaskId("task-1")
PLAN_ID = ValidationPlanId("plan-1")
OPENAPI_SNAPSHOT_ID = OpenAPIContextSnapshotId("snapshot-1")
EXECUTION_INTENT_ID = ExecutionIntentId("intent-1")


def reconstitute_attempt(
    *,
    attempt_id: ValidationAttemptId | None = ATTEMPT_ID,
    task_id: VerificationTaskId | None = TASK_ID,
    attempt_no: int | None = 1,
    plan_id: ValidationPlanId | None = PLAN_ID,
    openapi_snapshot_id: OpenAPIContextSnapshotId | None = OPENAPI_SNAPSHOT_ID,
    execution_intent_id: ExecutionIntentId | None = EXECUTION_INTENT_ID,
    status: ValidationAttemptStatus = ValidationAttemptStatus.EXECUTING,
    actual_send_count: int = 0,
    is_rerun: bool | None = False,
    previous_attempt_id: ValidationAttemptId | None = None,
    completed_at: datetime | None = None,
    evaluation_result_id: EvaluationResultId | None = None,
    evidence_bundle_id: EvidenceBundleId | None = None,
    conclusion: ValidationConclusion | None = None,
    created_at: datetime | None = CREATED_AT,
    started_at: datetime | None = STARTED_AT,
) -> ValidationAttempt:
    return ValidationAttempt._reconstitute(  # pyright: ignore[reportPrivateUsage]
        attempt_id=attempt_id,
        task_id=task_id,
        attempt_no=attempt_no,
        plan_id=plan_id,
        openapi_snapshot_id=openapi_snapshot_id,
        execution_intent_id=execution_intent_id,
        is_rerun=is_rerun,
        previous_attempt_id=previous_attempt_id,
        created_at=created_at,
        started_at=started_at,
        status=status,
        actual_send_count=actual_send_count,
        completed_at=completed_at,
        evaluation_result_id=evaluation_result_id,
        evidence_bundle_id=evidence_bundle_id,
        conclusion=conclusion,
    )


@pytest.mark.parametrize("actual_send_count", [0, 2, 3])
def test_reconstitutes_executing_attempt_with_valid_send_counts(
    actual_send_count: int,
) -> None:
    attempt = reconstitute_attempt(actual_send_count=actual_send_count)

    assert attempt.status is ValidationAttemptStatus.EXECUTING
    assert attempt.actual_send_count == actual_send_count
    assert attempt.conclusion is None


def test_reconstitutes_completed_attempt_with_all_final_values() -> None:
    attempt = reconstitute_attempt(
        status=ValidationAttemptStatus.COMPLETED,
        actual_send_count=3,
        completed_at=COMPLETED_AT,
        evaluation_result_id=EvaluationResultId("evaluation-1"),
        evidence_bundle_id=EvidenceBundleId("bundle-1"),
        conclusion=ValidationConclusion.PASSED,
    )

    assert attempt.status is ValidationAttemptStatus.COMPLETED
    assert attempt.completed_at == COMPLETED_AT
    assert attempt.conclusion is ValidationConclusion.PASSED


def test_reconstitutes_initial_and_rerun_attempts() -> None:
    initial_attempt = reconstitute_attempt()
    rerun_attempt = reconstitute_attempt(
        is_rerun=True,
        previous_attempt_id=ValidationAttemptId("attempt-0"),
    )

    assert initial_attempt.previous_attempt_id is None
    assert rerun_attempt.previous_attempt_id == ValidationAttemptId("attempt-0")


def test_reconstituted_executing_attempt_can_continue_to_three_sends() -> None:
    attempt = reconstitute_attempt(actual_send_count=2)

    attempt.record_http_send()

    assert attempt.actual_send_count == 3
    with pytest.raises(DomainError, match="three"):
        attempt.record_http_send()


def test_reconstituted_three_send_attempt_rejects_another_send() -> None:
    attempt = reconstitute_attempt(actual_send_count=3)

    with pytest.raises(DomainError, match="three"):
        attempt.record_http_send()


def test_reconstituted_executing_attempt_can_complete() -> None:
    attempt = reconstitute_attempt(actual_send_count=2)

    attempt.complete(
        evaluation_result_id=EvaluationResultId("evaluation-1"),
        evidence_bundle_id=EvidenceBundleId("bundle-1"),
        conclusion=ValidationConclusion.PASSED,
        completed_at=COMPLETED_AT,
    )

    assert attempt.status is ValidationAttemptStatus.COMPLETED


def test_reconstituted_completed_attempt_rejects_all_execution_behaviors() -> None:
    attempt = reconstitute_attempt(
        status=ValidationAttemptStatus.COMPLETED,
        completed_at=COMPLETED_AT,
        evaluation_result_id=EvaluationResultId("evaluation-1"),
        evidence_bundle_id=EvidenceBundleId("bundle-1"),
        conclusion=ValidationConclusion.PASSED,
    )

    with pytest.raises(IllegalStateTransitionError):
        attempt.record_http_send()
    with pytest.raises(IllegalStateTransitionError):
        attempt.complete(
            evaluation_result_id=EvaluationResultId("evaluation-2"),
            evidence_bundle_id=EvidenceBundleId("bundle-2"),
            conclusion=ValidationConclusion.SUSPECTED_DEFECT,
            completed_at=COMPLETED_AT + timedelta(seconds=1),
        )
    assert attempt.status is ValidationAttemptStatus.COMPLETED


@pytest.mark.parametrize("attempt_no", [0, -1])
def test_reconstitution_rejects_invalid_attempt_number(attempt_no: int) -> None:
    with pytest.raises(DomainError, match="attempt_no"):
        ValidationAttempt._reconstitute(  # pyright: ignore[reportPrivateUsage]
            attempt_id=ValidationAttemptId("attempt-1"),
            task_id=VerificationTaskId("task-1"),
            attempt_no=attempt_no,
            plan_id=ValidationPlanId("plan-1"),
            openapi_snapshot_id=OpenAPIContextSnapshotId("snapshot-1"),
            execution_intent_id=ExecutionIntentId("intent-1"),
            is_rerun=False,
            previous_attempt_id=None,
            created_at=CREATED_AT,
            started_at=STARTED_AT,
            status=ValidationAttemptStatus.EXECUTING,
            actual_send_count=0,
            completed_at=None,
            evaluation_result_id=None,
            evidence_bundle_id=None,
            conclusion=None,
        )


def test_reconstitution_rejects_invalid_rerun_relationships() -> None:
    with pytest.raises(DomainError, match="previous_attempt_id"):
        reconstitute_attempt(is_rerun=True)
    with pytest.raises(DomainError, match="previous_attempt_id"):
        reconstitute_attempt(previous_attempt_id=ValidationAttemptId("attempt-0"))


@pytest.mark.parametrize(
    "restore",
    [
        lambda: reconstitute_attempt(attempt_id=None),
        lambda: reconstitute_attempt(task_id=None),
        lambda: reconstitute_attempt(attempt_no=None),
        lambda: reconstitute_attempt(plan_id=None),
        lambda: reconstitute_attempt(openapi_snapshot_id=None),
        lambda: reconstitute_attempt(execution_intent_id=None),
        lambda: reconstitute_attempt(is_rerun=None),
        lambda: reconstitute_attempt(created_at=None),
        lambda: reconstitute_attempt(started_at=None),
    ],
)
def test_reconstitution_rejects_missing_fixed_bindings(
    restore: Callable[[], ValidationAttempt],
) -> None:
    with pytest.raises(DomainError, match="fixed binding"):
        restore()


@pytest.mark.parametrize("actual_send_count", [-1, 4])
def test_reconstitution_rejects_invalid_send_count(actual_send_count: int) -> None:
    with pytest.raises(DomainError, match="actual_send_count"):
        reconstitute_attempt(actual_send_count=actual_send_count)


@pytest.mark.parametrize(
    ("completed_at", "evaluation_result_id", "evidence_bundle_id", "conclusion"),
    [
        (COMPLETED_AT, None, None, None),
        (None, EvaluationResultId("evaluation-1"), None, None),
        (None, None, EvidenceBundleId("bundle-1"), None),
        (None, None, None, ValidationConclusion.PASSED),
    ],
)
def test_reconstitution_rejects_executing_attempt_with_final_values(
    completed_at: datetime | None,
    evaluation_result_id: EvaluationResultId | None,
    evidence_bundle_id: EvidenceBundleId | None,
    conclusion: ValidationConclusion | None,
) -> None:
    with pytest.raises(DomainError, match="EXECUTING"):
        reconstitute_attempt(
            completed_at=completed_at,
            evaluation_result_id=evaluation_result_id,
            evidence_bundle_id=evidence_bundle_id,
            conclusion=conclusion,
        )


@pytest.mark.parametrize(
    ("completed_at", "evaluation_result_id", "evidence_bundle_id", "conclusion"),
    [
        (
            None,
            EvaluationResultId("evaluation-1"),
            EvidenceBundleId("bundle-1"),
            ValidationConclusion.PASSED,
        ),
        (COMPLETED_AT, None, EvidenceBundleId("bundle-1"), ValidationConclusion.PASSED),
        (
            COMPLETED_AT,
            EvaluationResultId("evaluation-1"),
            None,
            ValidationConclusion.PASSED,
        ),
        (
            COMPLETED_AT,
            EvaluationResultId("evaluation-1"),
            EvidenceBundleId("bundle-1"),
            None,
        ),
    ],
)
def test_reconstitution_rejects_partial_completed_attempt(
    completed_at: datetime | None,
    evaluation_result_id: EvaluationResultId | None,
    evidence_bundle_id: EvidenceBundleId | None,
    conclusion: ValidationConclusion | None,
) -> None:
    with pytest.raises(DomainError, match="COMPLETED"):
        reconstitute_attempt(
            status=ValidationAttemptStatus.COMPLETED,
            completed_at=completed_at,
            evaluation_result_id=evaluation_result_id,
            evidence_bundle_id=evidence_bundle_id,
            conclusion=conclusion,
        )


def test_reconstitution_rejects_invalid_attempt_times() -> None:
    with pytest.raises(DomainError, match="started_at"):
        reconstitute_attempt(started_at=CREATED_AT - timedelta(seconds=1))
    with pytest.raises(DomainError, match="completed_at"):
        reconstitute_attempt(
            status=ValidationAttemptStatus.COMPLETED,
            completed_at=CREATED_AT,
            evaluation_result_id=EvaluationResultId("evaluation-1"),
            evidence_bundle_id=EvidenceBundleId("bundle-1"),
            conclusion=ValidationConclusion.PASSED,
        )
    with pytest.raises(DomainError, match="timezone-aware"):
        reconstitute_attempt(started_at=datetime(2026, 8, 3, 10, 0, 1))
    with pytest.raises(DomainError, match="timezone-aware"):
        reconstitute_attempt(created_at=datetime(2026, 8, 3, 10, 0))
    with pytest.raises(DomainError, match="timezone-aware"):
        reconstitute_attempt(
            status=ValidationAttemptStatus.COMPLETED,
            completed_at=datetime(2026, 8, 3, 10, 0, 2),
            evaluation_result_id=EvaluationResultId("evaluation-1"),
            evidence_bundle_id=EvidenceBundleId("bundle-1"),
            conclusion=ValidationConclusion.PASSED,
        )


def test_public_constructor_keeps_new_attempt_semantics() -> None:
    attempt = ValidationAttempt(
        attempt_id=ValidationAttemptId("attempt-1"),
        task_id=VerificationTaskId("task-1"),
        attempt_no=1,
        plan_id=ValidationPlanId("plan-1"),
        openapi_snapshot_id=OpenAPIContextSnapshotId("snapshot-1"),
        execution_intent_id=ExecutionIntentId("intent-1"),
        is_rerun=False,
        previous_attempt_id=None,
        created_at=CREATED_AT,
        started_at=STARTED_AT,
    )

    assert attempt.status is ValidationAttemptStatus.EXECUTING
    assert attempt.actual_send_count == 0
    assert attempt.completed_at is None
    assert attempt.conclusion is None


def test_reconstitution_is_not_exported_from_tasking_package() -> None:
    assert not hasattr(tasking, "_reconstitute")
