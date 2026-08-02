"""Verification task entity and its explicit lifecycle behaviors."""

from dataclasses import dataclass, field
from datetime import datetime

from apiguard.shared.enums import VerificationTaskStatus, VerificationTaskType
from apiguard.shared.errors import DomainError, IllegalStateTransitionError
from apiguard.shared.ids import ValidationPlanId, VerificationTaskId


@dataclass(slots=True)
class VerificationTask:
    """A stable verification objective with a preparation lifecycle."""

    task_id: VerificationTaskId
    task_type: VerificationTaskType
    verification_objective: str
    created_at: datetime
    _status: VerificationTaskStatus = field(
        default=VerificationTaskStatus.DRAFT,
        init=False,
        repr=False,
    )
    _current_confirmed_plan_id: ValidationPlanId | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _updated_at: datetime = field(init=False, repr=False)
    _cancelled_at: datetime | None = field(default=None, init=False, repr=False)
    _cancellation_reason: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._updated_at = self.created_at

    @property
    def status(self) -> VerificationTaskStatus:
        """Return the lifecycle state without allowing public assignment."""

        return self._status

    @property
    def current_confirmed_plan_id(self) -> ValidationPlanId | None:
        """Return the executable plan reference, if a plan is confirmed."""

        return self._current_confirmed_plan_id

    @property
    def updated_at(self) -> datetime:
        """Return the timestamp supplied by the latest successful behavior."""

        return self._updated_at

    @property
    def cancelled_at(self) -> datetime | None:
        """Return when the task was cancelled, if applicable."""

        return self._cancelled_at

    @property
    def cancellation_reason(self) -> str | None:
        """Return the caller-provided cancellation reason, if applicable."""

        return self._cancellation_reason

    def start_preparation(self, at: datetime) -> None:
        """Submit a draft task for preparation."""

        self._transition_from(
            VerificationTaskStatus.DRAFT,
            VerificationTaskStatus.PREPARING,
            "start_preparation",
            at,
        )

    def return_to_draft(self, at: datetime) -> None:
        """Return preparation to a draft when input needs revision."""

        self._transition_from(
            VerificationTaskStatus.PREPARING,
            VerificationTaskStatus.DRAFT,
            "return_to_draft",
            at,
        )

    def complete_preparation(self, at: datetime) -> None:
        """Record that a valid plan is ready for user confirmation."""

        self._transition_from(
            VerificationTaskStatus.PREPARING,
            VerificationTaskStatus.AWAITING_CONFIRMATION,
            "complete_preparation",
            at,
        )

    def request_plan_changes(self, at: datetime) -> None:
        """Return a pending plan to preparation at the user's request."""

        self._transition_from(
            VerificationTaskStatus.AWAITING_CONFIRMATION,
            VerificationTaskStatus.PREPARING,
            "request_plan_changes",
            at,
        )

    def confirm_plan(self, plan_id: ValidationPlanId | None, at: datetime) -> None:
        """Confirm the exact validated plan that may later be executed."""

        if plan_id is None:
            raise DomainError("A ValidationPlanId is required to confirm a plan.")
        self._require_current_state(
            VerificationTaskStatus.AWAITING_CONFIRMATION,
            "confirm_plan",
            VerificationTaskStatus.READY,
        )
        self._current_confirmed_plan_id = plan_id
        self._transition_from(
            VerificationTaskStatus.AWAITING_CONFIRMATION,
            VerificationTaskStatus.READY,
            "confirm_plan",
            at,
        )

    def restart_preparation(self, at: datetime) -> None:
        """Discard the executable-plan reference before preparing a new plan."""

        self._require_current_state(
            VerificationTaskStatus.READY,
            "restart_preparation",
            VerificationTaskStatus.PREPARING,
        )
        self._current_confirmed_plan_id = None
        self._transition_from(
            VerificationTaskStatus.READY,
            VerificationTaskStatus.PREPARING,
            "restart_preparation",
            at,
        )

    def cancel(self, reason: str, at: datetime) -> None:
        """Record cancellation; an application layer will gate active attempts."""

        if self._status is VerificationTaskStatus.CANCELLED:
            raise IllegalStateTransitionError(
                self._status,
                "cancel",
                VerificationTaskStatus.CANCELLED,
            )
        self._status = VerificationTaskStatus.CANCELLED
        self._cancelled_at = at
        self._cancellation_reason = reason
        self._updated_at = at

    def _transition_from(
        self,
        source: VerificationTaskStatus,
        target: VerificationTaskStatus,
        action: str,
        at: datetime,
    ) -> None:
        self._require_current_state(source, action, target)
        if (
            target is VerificationTaskStatus.READY
            and self._current_confirmed_plan_id is None
        ):
            raise DomainError(
                "READY tasks require a current confirmed ValidationPlanId."
            )
        self._status = target
        self._updated_at = at

    def _require_current_state(
        self,
        expected: VerificationTaskStatus,
        action: str,
        target: VerificationTaskStatus,
    ) -> None:
        if self._status is not expected:
            raise IllegalStateTransitionError(self._status, action, target)
