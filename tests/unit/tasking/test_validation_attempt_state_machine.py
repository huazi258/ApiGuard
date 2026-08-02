"""Tests for the ValidationAttempt execution lifecycle."""

from datetime import UTC, datetime, timedelta

import pytest

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

CREATED_AT = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)
STARTED_AT = CREATED_AT + timedelta(seconds=1)
COMPLETED_AT = STARTED_AT + timedelta(seconds=2)


def new_attempt(**overrides: object) -> ValidationAttempt:
    values: dict[str, object] = {
        "attempt_id": ValidationAttemptId("attempt-1"),
        "task_id": VerificationTaskId("task-1"),
        "attempt_no": 1,
        "plan_id": ValidationPlanId("plan-1"),
        "openapi_snapshot_id": OpenAPIContextSnapshotId("snapshot-1"),
        "execution_intent_id": ExecutionIntentId("intent-1"),
        "is_rerun": False,
        "previous_attempt_id": None,
        "created_at": CREATED_AT,
        "started_at": STARTED_AT,
    }
    values.update(overrides)
    return ValidationAttempt(**values)  # type: ignore[arg-type]


def complete_attempt(attempt: ValidationAttempt) -> None:
    attempt.complete(
        evaluation_result_id=EvaluationResultId("evaluation-1"),
        evidence_bundle_id=EvidenceBundleId("bundle-1"),
        conclusion=ValidationConclusion.PASSED,
        completed_at=COMPLETED_AT,
    )


def test_new_attempt_is_executing_with_no_final_result() -> None:
    attempt = new_attempt()

    assert attempt.status is ValidationAttemptStatus.EXECUTING
    assert attempt.actual_send_count == 0
    assert attempt.completed_at is None
    assert attempt.evaluation_result_id is None
    assert attempt.evidence_bundle_id is None
    assert attempt.conclusion is None


def test_new_attempt_keeps_fixed_bindings_and_explicit_times() -> None:
    attempt = new_attempt()

    assert attempt.attempt_id == ValidationAttemptId("attempt-1")
    assert attempt.task_id == VerificationTaskId("task-1")
    assert attempt.attempt_no == 1
    assert attempt.plan_id == ValidationPlanId("plan-1")
    assert attempt.openapi_snapshot_id == OpenAPIContextSnapshotId("snapshot-1")
    assert attempt.execution_intent_id == ExecutionIntentId("intent-1")
    assert attempt.created_at == CREATED_AT
    assert attempt.started_at == STARTED_AT


@pytest.mark.parametrize("attempt_no", [0, -1])
def test_attempt_number_must_be_positive(attempt_no: int) -> None:
    with pytest.raises(DomainError, match="attempt_no"):
        new_attempt(attempt_no=attempt_no)


def test_initial_attempt_cannot_reference_a_previous_attempt() -> None:
    with pytest.raises(DomainError, match="previous_attempt_id"):
        new_attempt(previous_attempt_id=ValidationAttemptId("attempt-0"))


def test_rerun_requires_and_retains_previous_attempt() -> None:
    previous_attempt_id = ValidationAttemptId("attempt-0")
    attempt = new_attempt(is_rerun=True, previous_attempt_id=previous_attempt_id)

    assert attempt.is_rerun is True
    assert attempt.previous_attempt_id == previous_attempt_id


def test_rerun_without_previous_attempt_is_rejected() -> None:
    with pytest.raises(DomainError, match="previous_attempt_id"):
        new_attempt(is_rerun=True)


def test_first_three_actual_sends_are_recorded() -> None:
    attempt = new_attempt()

    attempt.record_http_send()
    attempt.record_http_send()
    attempt.record_http_send()

    assert attempt.actual_send_count == 3


def test_fourth_actual_send_is_rejected_without_changing_count() -> None:
    attempt = new_attempt()
    for _ in range(3):
        attempt.record_http_send()

    with pytest.raises(DomainError, match="three"):
        attempt.record_http_send()

    assert attempt.actual_send_count == 3


def test_completion_binds_all_final_results_atomically() -> None:
    attempt = new_attempt()

    complete_attempt(attempt)

    assert attempt.status is ValidationAttemptStatus.COMPLETED
    assert attempt.completed_at == COMPLETED_AT
    assert attempt.evaluation_result_id == EvaluationResultId("evaluation-1")
    assert attempt.evidence_bundle_id == EvidenceBundleId("bundle-1")
    assert attempt.conclusion is ValidationConclusion.PASSED


@pytest.mark.parametrize(
    ("evaluation_result_id", "evidence_bundle_id", "conclusion", "completed_at"),
    [
        (None, EvidenceBundleId("bundle-1"), ValidationConclusion.PASSED, COMPLETED_AT),
        (
            EvaluationResultId("evaluation-1"),
            None,
            ValidationConclusion.PASSED,
            COMPLETED_AT,
        ),
        (
            EvaluationResultId("evaluation-1"),
            EvidenceBundleId("bundle-1"),
            None,
            COMPLETED_AT,
        ),
        (
            EvaluationResultId("evaluation-1"),
            EvidenceBundleId("bundle-1"),
            ValidationConclusion.PASSED,
            None,
        ),
    ],
)
def test_completion_rejects_missing_final_values(
    evaluation_result_id: EvaluationResultId | None,
    evidence_bundle_id: EvidenceBundleId | None,
    conclusion: ValidationConclusion | None,
    completed_at: datetime | None,
) -> None:
    attempt = new_attempt()

    with pytest.raises(DomainError, match="all final"):
        attempt.complete(
            evaluation_result_id=evaluation_result_id,
            evidence_bundle_id=evidence_bundle_id,
            conclusion=conclusion,
            completed_at=completed_at,
        )

    assert attempt.status is ValidationAttemptStatus.EXECUTING
    assert attempt.conclusion is None


def test_completed_attempt_rejects_second_completion_and_sends() -> None:
    attempt = new_attempt()
    complete_attempt(attempt)

    with pytest.raises(IllegalStateTransitionError):
        complete_attempt(attempt)
    with pytest.raises(IllegalStateTransitionError):
        attempt.record_http_send()


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("evaluation_result_id", EvaluationResultId("evaluation-2")),
        ("evidence_bundle_id", EvidenceBundleId("bundle-2")),
        ("conclusion", ValidationConclusion.SUSPECTED_DEFECT),
        ("completed_at", COMPLETED_AT + timedelta(seconds=1)),
    ],
)
def test_completed_final_results_cannot_be_replaced(
    attribute: str,
    value: object,
) -> None:
    attempt = new_attempt()
    complete_attempt(attempt)

    with pytest.raises(AttributeError):
        setattr(attempt, attribute, value)


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("task_id", VerificationTaskId("task-2")),
        ("plan_id", ValidationPlanId("plan-2")),
        ("openapi_snapshot_id", OpenAPIContextSnapshotId("snapshot-2")),
        ("execution_intent_id", ExecutionIntentId("intent-2")),
    ],
)
def test_public_fixed_bindings_cannot_be_replaced(
    attribute: str,
    value: object,
) -> None:
    attempt = new_attempt()

    with pytest.raises(AttributeError):
        setattr(attempt, attribute, value)


def test_status_is_not_publicly_assignable() -> None:
    attempt = new_attempt()

    with pytest.raises(AttributeError):
        attempt.status = ValidationAttemptStatus.COMPLETED  # pyright: ignore[reportAttributeAccessIssue]


def test_attempt_has_no_verification_task_state() -> None:
    attempt = new_attempt()

    assert not hasattr(attempt, "verification_task_status")
