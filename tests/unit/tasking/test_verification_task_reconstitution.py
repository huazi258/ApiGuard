"""Tests for restoring persisted VerificationTask state without replaying behavior."""

from datetime import UTC, datetime, timedelta

import pytest

import apiguard.tasking as tasking
from apiguard.shared.enums import VerificationTaskStatus, VerificationTaskType
from apiguard.shared.errors import DomainError, IllegalStateTransitionError
from apiguard.shared.ids import ValidationPlanId, VerificationTaskId
from apiguard.tasking.models import VerificationTask

CREATED_AT = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
UPDATED_AT = CREATED_AT + timedelta(minutes=1)
CANCELLED_AT = UPDATED_AT + timedelta(minutes=1)
PLAN_ID = ValidationPlanId("plan-1")


def reconstitute_task(
    *,
    status: VerificationTaskStatus = VerificationTaskStatus.DRAFT,
    current_confirmed_plan_id: ValidationPlanId | None = None,
    updated_at: datetime = UPDATED_AT,
    cancelled_at: datetime | None = None,
    cancellation_reason: str | None = None,
) -> VerificationTask:
    return VerificationTask._reconstitute(  # pyright: ignore[reportPrivateUsage]
        task_id=VerificationTaskId("task-1"),
        task_type=VerificationTaskType.BUSINESS_RULE,
        verification_objective="Reject cancellation of an already-paid order.",
        created_at=CREATED_AT,
        status=status,
        current_confirmed_plan_id=current_confirmed_plan_id,
        updated_at=updated_at,
        cancelled_at=cancelled_at,
        cancellation_reason=cancellation_reason,
    )


@pytest.mark.parametrize(
    ("status", "plan_id", "cancelled_at", "reason"),
    [
        (VerificationTaskStatus.DRAFT, None, None, None),
        (VerificationTaskStatus.PREPARING, None, None, None),
        (VerificationTaskStatus.AWAITING_CONFIRMATION, None, None, None),
        (VerificationTaskStatus.READY, PLAN_ID, None, None),
        (VerificationTaskStatus.CANCELLED, PLAN_ID, CANCELLED_AT, "User cancelled."),
        (VerificationTaskStatus.CANCELLED, None, CANCELLED_AT, "User cancelled."),
    ],
)
def test_reconstitutes_legal_task_states(
    status: VerificationTaskStatus,
    plan_id: ValidationPlanId | None,
    cancelled_at: datetime | None,
    reason: str | None,
) -> None:
    task = reconstitute_task(
        status=status,
        current_confirmed_plan_id=plan_id,
        updated_at=CANCELLED_AT
        if status is VerificationTaskStatus.CANCELLED
        else UPDATED_AT,
        cancelled_at=cancelled_at,
        cancellation_reason=reason,
    )

    assert task.status is status
    assert task.current_confirmed_plan_id == plan_id
    assert task.cancelled_at == cancelled_at
    assert task.cancellation_reason == reason


def test_reconstituted_ready_task_can_restart_preparation() -> None:
    task = reconstitute_task(
        status=VerificationTaskStatus.READY,
        current_confirmed_plan_id=PLAN_ID,
    )

    task.restart_preparation(CANCELLED_AT)

    assert task.status is VerificationTaskStatus.PREPARING
    assert task.current_confirmed_plan_id is None


def test_reconstituted_awaiting_confirmation_task_can_confirm_plan() -> None:
    task = reconstitute_task(status=VerificationTaskStatus.AWAITING_CONFIRMATION)

    task.confirm_plan(PLAN_ID, CANCELLED_AT)

    assert task.status is VerificationTaskStatus.READY
    assert task.current_confirmed_plan_id == PLAN_ID


def test_reconstituted_cancelled_task_remains_terminal() -> None:
    task = reconstitute_task(
        status=VerificationTaskStatus.CANCELLED,
        cancelled_at=CANCELLED_AT,
        cancellation_reason="User cancelled.",
        updated_at=CANCELLED_AT,
    )

    with pytest.raises(IllegalStateTransitionError):
        task.start_preparation(CANCELLED_AT + timedelta(minutes=1))


@pytest.mark.parametrize(
    ("status", "plan_id"),
    [
        (VerificationTaskStatus.DRAFT, PLAN_ID),
        (VerificationTaskStatus.PREPARING, PLAN_ID),
        (VerificationTaskStatus.AWAITING_CONFIRMATION, PLAN_ID),
    ],
)
def test_reconstitution_rejects_plan_outside_ready_or_cancelled(
    status: VerificationTaskStatus,
    plan_id: ValidationPlanId,
) -> None:
    with pytest.raises(DomainError, match="plan"):
        reconstitute_task(status=status, current_confirmed_plan_id=plan_id)


def test_reconstitution_rejects_ready_without_confirmed_plan() -> None:
    with pytest.raises(DomainError, match="READY"):
        reconstitute_task(status=VerificationTaskStatus.READY)


@pytest.mark.parametrize(
    ("cancelled_at", "reason"),
    [(None, "User cancelled."), (CANCELLED_AT, None)],
)
def test_reconstitution_rejects_cancelled_without_complete_cancellation_facts(
    cancelled_at: datetime | None,
    reason: str | None,
) -> None:
    with pytest.raises(DomainError, match="CANCELLED"):
        reconstitute_task(
            status=VerificationTaskStatus.CANCELLED,
            cancelled_at=cancelled_at,
            cancellation_reason=reason,
            updated_at=CANCELLED_AT,
        )


@pytest.mark.parametrize(
    "status",
    [
        VerificationTaskStatus.DRAFT,
        VerificationTaskStatus.PREPARING,
        VerificationTaskStatus.AWAITING_CONFIRMATION,
        VerificationTaskStatus.READY,
    ],
)
def test_reconstitution_rejects_cancellation_facts_on_active_tasks(
    status: VerificationTaskStatus,
) -> None:
    with pytest.raises(DomainError, match="cancellation"):
        reconstitute_task(
            status=status,
            current_confirmed_plan_id=PLAN_ID
            if status is VerificationTaskStatus.READY
            else None,
            cancelled_at=CANCELLED_AT,
            cancellation_reason="Unexpected.",
        )


def test_reconstitution_rejects_invalid_task_times() -> None:
    with pytest.raises(DomainError, match="updated_at"):
        reconstitute_task(updated_at=CREATED_AT - timedelta(seconds=1))
    with pytest.raises(DomainError, match="timezone-aware"):
        reconstitute_task(updated_at=datetime(2026, 8, 3, 9, 1))
    with pytest.raises(DomainError, match="timezone-aware"):
        VerificationTask._reconstitute(  # pyright: ignore[reportPrivateUsage]
            task_id=VerificationTaskId("task-1"),
            task_type=VerificationTaskType.BUSINESS_RULE,
            verification_objective="Objective.",
            created_at=datetime(2026, 8, 3, 9, 0),
            status=VerificationTaskStatus.DRAFT,
            current_confirmed_plan_id=None,
            updated_at=UPDATED_AT,
            cancelled_at=None,
            cancellation_reason=None,
        )
    with pytest.raises(DomainError, match="cancelled_at"):
        reconstitute_task(
            status=VerificationTaskStatus.CANCELLED,
            cancelled_at=CREATED_AT - timedelta(seconds=1),
            cancellation_reason="User cancelled.",
            updated_at=CANCELLED_AT,
        )
    with pytest.raises(DomainError, match="updated_at"):
        reconstitute_task(
            status=VerificationTaskStatus.CANCELLED,
            cancelled_at=CANCELLED_AT,
            cancellation_reason="User cancelled.",
        )


def test_public_constructor_keeps_new_task_semantics() -> None:
    task = VerificationTask(
        task_id=VerificationTaskId("task-1"),
        task_type=VerificationTaskType.BUSINESS_RULE,
        verification_objective="Objective.",
        created_at=CREATED_AT,
    )

    assert task.status is VerificationTaskStatus.DRAFT
    assert task.updated_at == CREATED_AT
    assert task.current_confirmed_plan_id is None
    assert task.cancelled_at is None


def test_reconstitution_is_not_exported_from_tasking_package() -> None:
    assert not hasattr(tasking, "_reconstitute")
