"""Verification task entity and its explicit lifecycle behaviors."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

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


@dataclass(slots=True, init=False)
class ValidationAttempt:
    """A single execution lifecycle with fixed input bindings and final results."""

    MAX_HTTP_SENDS_PER_ATTEMPT: ClassVar[int] = 3

    _attempt_id: ValidationAttemptId = field(repr=False)
    _task_id: VerificationTaskId = field(repr=False)
    _attempt_no: int = field(repr=False)
    _plan_id: ValidationPlanId = field(repr=False)
    _openapi_snapshot_id: OpenAPIContextSnapshotId = field(repr=False)
    _execution_intent_id: ExecutionIntentId = field(repr=False)
    _is_rerun: bool = field(repr=False)
    _previous_attempt_id: ValidationAttemptId | None = field(repr=False)
    _created_at: datetime = field(repr=False)
    _started_at: datetime = field(repr=False)
    _status: ValidationAttemptStatus = field(repr=False)
    _actual_send_count: int = field(repr=False)
    _completed_at: datetime | None = field(repr=False)
    _evaluation_result_id: EvaluationResultId | None = field(repr=False)
    _evidence_bundle_id: EvidenceBundleId | None = field(repr=False)
    _conclusion: ValidationConclusion | None = field(repr=False)

    def __init__(
        self,
        attempt_id: ValidationAttemptId,
        task_id: VerificationTaskId,
        attempt_no: int,
        plan_id: ValidationPlanId,
        openapi_snapshot_id: OpenAPIContextSnapshotId,
        execution_intent_id: ExecutionIntentId,
        is_rerun: bool,
        previous_attempt_id: ValidationAttemptId | None,
        created_at: datetime,
        started_at: datetime,
    ) -> None:
        if attempt_no <= 0:
            raise DomainError("attempt_no must be a positive integer.")
        if is_rerun and previous_attempt_id is None:
            raise DomainError("Reruns require a previous_attempt_id.")
        if not is_rerun and previous_attempt_id is not None:
            raise DomainError("Initial attempts cannot have a previous_attempt_id.")

        self._attempt_id = attempt_id
        self._task_id = task_id
        self._attempt_no = attempt_no
        self._plan_id = plan_id
        self._openapi_snapshot_id = openapi_snapshot_id
        self._execution_intent_id = execution_intent_id
        self._is_rerun = is_rerun
        self._previous_attempt_id = previous_attempt_id
        self._created_at = created_at
        self._started_at = started_at
        self._status = ValidationAttemptStatus.EXECUTING
        self._actual_send_count = 0
        self._completed_at = None
        self._evaluation_result_id = None
        self._evidence_bundle_id = None
        self._conclusion = None

    @property
    def attempt_id(self) -> ValidationAttemptId:
        return self._attempt_id

    @property
    def task_id(self) -> VerificationTaskId:
        return self._task_id

    @property
    def attempt_no(self) -> int:
        return self._attempt_no

    @property
    def plan_id(self) -> ValidationPlanId:
        return self._plan_id

    @property
    def openapi_snapshot_id(self) -> OpenAPIContextSnapshotId:
        return self._openapi_snapshot_id

    @property
    def execution_intent_id(self) -> ExecutionIntentId:
        return self._execution_intent_id

    @property
    def is_rerun(self) -> bool:
        return self._is_rerun

    @property
    def previous_attempt_id(self) -> ValidationAttemptId | None:
        return self._previous_attempt_id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def started_at(self) -> datetime:
        return self._started_at

    @property
    def status(self) -> ValidationAttemptStatus:
        return self._status

    @property
    def actual_send_count(self) -> int:
        return self._actual_send_count

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    @property
    def evaluation_result_id(self) -> EvaluationResultId | None:
        return self._evaluation_result_id

    @property
    def evidence_bundle_id(self) -> EvidenceBundleId | None:
        return self._evidence_bundle_id

    @property
    def conclusion(self) -> ValidationConclusion | None:
        return self._conclusion

    def record_http_send(self) -> None:
        """Record one actual request dispatch, including a technical retry."""

        self._require_executing(
            "record_http_send",
            ValidationAttemptStatus.EXECUTING,
        )
        if self._actual_send_count >= self.MAX_HTTP_SENDS_PER_ATTEMPT:
            raise DomainError("An attempt cannot send more than three HTTP requests.")
        self._actual_send_count += 1

    def complete(
        self,
        evaluation_result_id: EvaluationResultId | None,
        evidence_bundle_id: EvidenceBundleId | None,
        conclusion: ValidationConclusion | None,
        completed_at: datetime | None,
    ) -> None:
        """Atomically bind final results and close an executing attempt."""

        if (
            evaluation_result_id is None
            or evidence_bundle_id is None
            or conclusion is None
            or completed_at is None
        ):
            raise DomainError("Completion requires all final values.")
        self._require_executing("complete", ValidationAttemptStatus.COMPLETED)
        self._evaluation_result_id = evaluation_result_id
        self._evidence_bundle_id = evidence_bundle_id
        self._conclusion = conclusion
        self._completed_at = completed_at
        self._status = ValidationAttemptStatus.COMPLETED

    def _require_executing(
        self,
        action: str,
        target: ValidationAttemptStatus,
    ) -> None:
        if self._status is not ValidationAttemptStatus.EXECUTING:
            raise IllegalStateTransitionError(self._status, action, target)
