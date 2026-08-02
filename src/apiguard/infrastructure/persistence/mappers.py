"""Explicit Task and Attempt conversions without Session or transaction behavior."""

from apiguard.infrastructure.persistence.orm import (
    ValidationAttemptRow,
    VerificationTaskRow,
)
from apiguard.infrastructure.persistence.values import (
    bool_from_database,
    bool_to_database,
    datetime_from_database,
    datetime_to_database,
    enum_from_database,
    enum_to_database,
    id_from_database,
    id_to_database,
)
from apiguard.shared.enums import (
    ValidationAttemptStatus,
    ValidationConclusion,
    VerificationTaskStatus,
    VerificationTaskType,
)
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


def task_to_row(task: VerificationTask) -> VerificationTaskRow:
    """Build a new row while leaving future task inputs as SQL NULL."""

    return VerificationTaskRow(
        task_id=id_to_database(task.task_id),
        task_type=enum_to_database(task.task_type),
        verification_objective=task.verification_objective,
        status=enum_to_database(task.status),
        current_confirmed_plan_id=id_to_database(task.current_confirmed_plan_id),
        created_at=datetime_to_database(task.created_at),
        updated_at=datetime_to_database(task.updated_at),
        cancelled_at=datetime_to_database(task.cancelled_at),
        cancellation_reason=task.cancellation_reason,
    )


def task_from_row(row: VerificationTaskRow) -> VerificationTask:
    """Restore a task only through its domain reconstitution contract."""

    return VerificationTask._reconstitute(  # pyright: ignore[reportPrivateUsage]
        task_id=_required(id_from_database(row.task_id, VerificationTaskId), "task_id"),
        task_type=_required(
            enum_from_database(row.task_type, VerificationTaskType), "task_type"
        ),
        verification_objective=row.verification_objective,
        created_at=_required(datetime_from_database(row.created_at), "created_at"),
        status=_required(
            enum_from_database(row.status, VerificationTaskStatus), "status"
        ),
        current_confirmed_plan_id=id_from_database(
            row.current_confirmed_plan_id, ValidationPlanId
        ),
        updated_at=_required(datetime_from_database(row.updated_at), "updated_at"),
        cancelled_at=datetime_from_database(row.cancelled_at),
        cancellation_reason=row.cancellation_reason,
    )


def apply_task_state_to_row(task: VerificationTask, row: VerificationTaskRow) -> None:
    """Apply only M1-owned task state without touching future input columns."""

    row.status = _required(enum_to_database(task.status), "status")
    row.current_confirmed_plan_id = id_to_database(task.current_confirmed_plan_id)
    row.updated_at = _required(datetime_to_database(task.updated_at), "updated_at")
    row.cancelled_at = datetime_to_database(task.cancelled_at)
    row.cancellation_reason = task.cancellation_reason


def attempt_to_row(attempt: ValidationAttempt) -> ValidationAttemptRow:
    """Build a complete structural row from an attempt's public state."""

    return ValidationAttemptRow(
        attempt_id=id_to_database(attempt.attempt_id),
        task_id=id_to_database(attempt.task_id),
        attempt_no=attempt.attempt_no,
        plan_id=id_to_database(attempt.plan_id),
        openapi_snapshot_id=id_to_database(attempt.openapi_snapshot_id),
        status=enum_to_database(attempt.status),
        execution_intent_id=id_to_database(attempt.execution_intent_id),
        is_rerun=_required(bool_to_database(attempt.is_rerun), "is_rerun"),
        previous_attempt_id=id_to_database(attempt.previous_attempt_id),
        created_at=datetime_to_database(attempt.created_at),
        started_at=datetime_to_database(attempt.started_at),
        completed_at=datetime_to_database(attempt.completed_at),
        actual_send_count=attempt.actual_send_count,
        evaluation_result_id=id_to_database(attempt.evaluation_result_id),
        evidence_bundle_id=id_to_database(attempt.evidence_bundle_id),
        conclusion=enum_to_database(attempt.conclusion),
    )


def attempt_from_row(row: ValidationAttemptRow) -> ValidationAttempt:
    """Restore an attempt only through its domain reconstitution contract."""

    return ValidationAttempt._reconstitute(  # pyright: ignore[reportPrivateUsage]
        attempt_id=id_from_database(row.attempt_id, ValidationAttemptId),
        task_id=id_from_database(row.task_id, VerificationTaskId),
        attempt_no=row.attempt_no,
        plan_id=id_from_database(row.plan_id, ValidationPlanId),
        openapi_snapshot_id=id_from_database(
            row.openapi_snapshot_id, OpenAPIContextSnapshotId
        ),
        execution_intent_id=id_from_database(
            row.execution_intent_id, ExecutionIntentId
        ),
        is_rerun=bool_from_database(row.is_rerun),
        previous_attempt_id=id_from_database(
            row.previous_attempt_id, ValidationAttemptId
        ),
        created_at=datetime_from_database(row.created_at),
        started_at=datetime_from_database(row.started_at),
        status=_required(
            enum_from_database(row.status, ValidationAttemptStatus), "status"
        ),
        actual_send_count=row.actual_send_count,
        completed_at=datetime_from_database(row.completed_at),
        evaluation_result_id=id_from_database(
            row.evaluation_result_id, EvaluationResultId
        ),
        evidence_bundle_id=id_from_database(row.evidence_bundle_id, EvidenceBundleId),
        conclusion=enum_from_database(row.conclusion, ValidationConclusion),
    )


def apply_attempt_state_to_row(
    attempt: ValidationAttempt,
    row: ValidationAttemptRow,
) -> None:
    """Apply mutable attempt state without replacing fixed execution bindings."""

    row.status = _required(enum_to_database(attempt.status), "status")
    row.actual_send_count = attempt.actual_send_count
    row.completed_at = datetime_to_database(attempt.completed_at)
    row.evaluation_result_id = id_to_database(attempt.evaluation_result_id)
    row.evidence_bundle_id = id_to_database(attempt.evidence_bundle_id)
    row.conclusion = enum_to_database(attempt.conclusion)


def _required[ValueT](value: ValueT | None, field_name: str) -> ValueT:
    if value is None:
        raise ValueError(f"{field_name} is required for persistence mapping.")
    return value
