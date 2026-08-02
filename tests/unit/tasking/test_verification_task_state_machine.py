"""Tests for the VerificationTask preparation and confirmation lifecycle."""

import ast
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apiguard.shared.enums import VerificationTaskStatus, VerificationTaskType
from apiguard.shared.errors import DomainError, IllegalStateTransitionError
from apiguard.shared.ids import ValidationPlanId, VerificationTaskId
from apiguard.tasking.models import VerificationTask

CREATED_AT = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
PREPARING_AT = CREATED_AT + timedelta(minutes=1)
AWAITING_CONFIRMATION_AT = PREPARING_AT + timedelta(minutes=1)
READY_AT = AWAITING_CONFIRMATION_AT + timedelta(minutes=1)
CANCELLED_AT = READY_AT + timedelta(minutes=1)
PLAN_ID = ValidationPlanId("plan-1")
PROJECT_ROOT = Path(__file__).parents[3]
TASKING_DIRECTORY = PROJECT_ROOT / "src" / "apiguard" / "tasking"


def new_task() -> VerificationTask:
    return VerificationTask(
        task_id=VerificationTaskId("task-1"),
        task_type=VerificationTaskType.BUSINESS_RULE,
        verification_objective="Reject cancellation of an already-paid order.",
        created_at=CREATED_AT,
    )


def task_awaiting_confirmation() -> VerificationTask:
    task = new_task()
    task.start_preparation(PREPARING_AT)
    task.complete_preparation(AWAITING_CONFIRMATION_AT)
    return task


def task_ready() -> VerificationTask:
    task = task_awaiting_confirmation()
    task.confirm_plan(PLAN_ID, READY_AT)
    return task


def test_new_task_starts_as_draft_with_explicit_created_time() -> None:
    task = new_task()

    assert task.status is VerificationTaskStatus.DRAFT
    assert task.created_at == CREATED_AT
    assert task.updated_at == CREATED_AT
    assert task.current_confirmed_plan_id is None
    assert task.cancelled_at is None
    assert task.cancellation_reason is None


def test_preparation_transitions_follow_the_frozen_happy_path() -> None:
    task = new_task()

    task.start_preparation(PREPARING_AT)
    assert task.status is VerificationTaskStatus.PREPARING
    assert task.updated_at == PREPARING_AT

    task.complete_preparation(AWAITING_CONFIRMATION_AT)
    assert task.status is VerificationTaskStatus.AWAITING_CONFIRMATION
    assert task.updated_at == AWAITING_CONFIRMATION_AT

    task.confirm_plan(PLAN_ID, READY_AT)
    assert task.status is VerificationTaskStatus.READY
    assert task.current_confirmed_plan_id == PLAN_ID
    assert task.updated_at == READY_AT


def test_preparing_can_return_to_draft() -> None:
    task = new_task()
    task.start_preparation(PREPARING_AT)

    task.return_to_draft(AWAITING_CONFIRMATION_AT)

    assert task.status is VerificationTaskStatus.DRAFT
    assert task.updated_at == AWAITING_CONFIRMATION_AT


def test_awaiting_confirmation_can_request_repreparation() -> None:
    task = task_awaiting_confirmation()

    task.request_plan_changes(READY_AT)

    assert task.status is VerificationTaskStatus.PREPARING
    assert task.updated_at == READY_AT


def test_ready_can_restart_preparation_and_clears_confirmed_plan() -> None:
    task = task_ready()

    task.restart_preparation(CANCELLED_AT)

    assert task.status is VerificationTaskStatus.PREPARING
    assert task.current_confirmed_plan_id is None
    assert task.updated_at == CANCELLED_AT


@pytest.mark.parametrize(
    "task_factory",
    [new_task, lambda: _preparing_task(), task_awaiting_confirmation, task_ready],
)
def test_cancellation_is_allowed_before_attempt_execution(
    task_factory: Callable[[], VerificationTask],
) -> None:
    task = task_factory()

    task.cancel("The user chose not to execute.", CANCELLED_AT)

    assert task.status is VerificationTaskStatus.CANCELLED


def _preparing_task() -> VerificationTask:
    task = new_task()
    task.start_preparation(PREPARING_AT)
    return task


def test_illegal_reverse_transitions_are_rejected_with_state_details() -> None:
    draft = new_task()
    with pytest.raises(IllegalStateTransitionError) as draft_error:
        draft.return_to_draft(CANCELLED_AT)
    assert draft_error.value.current_state is VerificationTaskStatus.DRAFT
    assert draft_error.value.requested_action == "return_to_draft"
    assert draft_error.value.target_state is VerificationTaskStatus.DRAFT

    preparing = _preparing_task()
    with pytest.raises(IllegalStateTransitionError):
        preparing.start_preparation(CANCELLED_AT)

    awaiting_confirmation = task_awaiting_confirmation()
    with pytest.raises(IllegalStateTransitionError):
        awaiting_confirmation.complete_preparation(CANCELLED_AT)

    ready = task_ready()
    with pytest.raises(IllegalStateTransitionError):
        ready.confirm_plan(PLAN_ID, CANCELLED_AT)


def test_only_awaiting_confirmation_can_confirm_a_plan() -> None:
    task = new_task()

    with pytest.raises(IllegalStateTransitionError):
        task.confirm_plan(PLAN_ID, PREPARING_AT)


def test_confirming_without_a_plan_id_fails() -> None:
    task = task_awaiting_confirmation()

    with pytest.raises(DomainError, match="ValidationPlanId"):
        task.confirm_plan(None, READY_AT)


def test_status_is_not_publicly_assignable() -> None:
    task = new_task()

    with pytest.raises(AttributeError):
        task.status = VerificationTaskStatus.READY  # pyright: ignore[reportAttributeAccessIssue]


def test_cancelled_task_rejects_all_business_transitions() -> None:
    task = task_ready()
    task.cancel("No longer needed.", CANCELLED_AT)

    with pytest.raises(IllegalStateTransitionError):
        task.start_preparation(CANCELLED_AT + timedelta(minutes=1))
    with pytest.raises(IllegalStateTransitionError):
        task.return_to_draft(CANCELLED_AT + timedelta(minutes=1))
    with pytest.raises(IllegalStateTransitionError):
        task.complete_preparation(CANCELLED_AT + timedelta(minutes=1))
    with pytest.raises(IllegalStateTransitionError):
        task.request_plan_changes(CANCELLED_AT + timedelta(minutes=1))
    with pytest.raises(IllegalStateTransitionError):
        task.restart_preparation(CANCELLED_AT + timedelta(minutes=1))
    with pytest.raises(IllegalStateTransitionError):
        task.confirm_plan(PLAN_ID, CANCELLED_AT + timedelta(minutes=1))
    with pytest.raises(IllegalStateTransitionError):
        task.cancel("Already cancelled.", CANCELLED_AT + timedelta(minutes=1))


def test_cancellation_records_explicit_time_and_reason() -> None:
    task = task_ready()

    task.cancel("The test environment will be reset.", CANCELLED_AT)

    assert task.status is VerificationTaskStatus.CANCELLED
    assert task.cancelled_at == CANCELLED_AT
    assert task.cancellation_reason == "The test environment will be reset."
    assert task.updated_at == CANCELLED_AT


def test_verification_task_has_no_authoritative_conclusion() -> None:
    task = new_task()

    assert not hasattr(task, "conclusion")


def test_tasking_has_no_framework_or_infrastructure_imports() -> None:
    forbidden_prefixes = (
        "fastapi",
        "httpx",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "apiguard.infrastructure",
    )

    for path in TASKING_DIRECTORY.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ] + [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]

        assert not any(
            module.startswith(forbidden_prefixes) for module in imported_modules
        )
