"""SQLAlchemy implementations of the application persistence ports."""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from apiguard.application.errors import (
    AttemptStateConflict,
    PersistenceConflict,
    PersistenceUnavailable,
    TaskStateConflict,
    ValidationAttemptNotFound,
    VerificationTaskNotFound,
)
from apiguard.application.ports import DerivedReportRecord, EvidenceBundleRecord
from apiguard.infrastructure.persistence.mappers import (
    apply_attempt_state_to_row,
    apply_task_state_to_row,
    attempt_from_row,
    attempt_to_row,
    task_from_row,
    task_to_row,
)
from apiguard.infrastructure.persistence.orm import (
    DerivedReportRow,
    EvidenceBundleRow,
    ValidationAttemptRow,
    VerificationTaskRow,
)
from apiguard.infrastructure.persistence.values import (
    datetime_to_database,
    id_to_database,
)
from apiguard.shared.enums import ValidationAttemptStatus
from apiguard.shared.ids import (
    ExecutionIntentId,
    ValidationAttemptId,
    VerificationTaskId,
)
from apiguard.tasking.models import ValidationAttempt, VerificationTask


class SqlAlchemyTaskRepository:
    """Task repository using a session owned by its Unit of Work."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: VerificationTask) -> None:
        self._session.add(task_to_row(task))

    def get(self, task_id: VerificationTaskId) -> VerificationTask | None:
        row = _database_operation(
            lambda: self._session.get(
                VerificationTaskRow, _required_id(task_id, "task_id")
            )
        )
        return None if row is None else task_from_row(row)

    def save(self, task: VerificationTask) -> None:
        row = _database_operation(
            lambda: self._session.get(
                VerificationTaskRow, _required_id(task.task_id, "task_id")
            )
        )
        if row is None:
            raise VerificationTaskNotFound(
                f"Verification task {task.task_id} was not found."
            )
        if (
            row.task_id != _required_id(task.task_id, "task_id")
            or row.task_type != task.task_type.value
            or row.verification_objective != task.verification_objective
            or row.created_at != datetime_to_database(task.created_at)
        ):
            raise TaskStateConflict("Task fixed facts cannot be changed when saving.")
        apply_task_state_to_row(task, row)


class SqlAlchemyAttemptRepository:
    """Attempt repository using a session owned by its Unit of Work."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, attempt: ValidationAttempt) -> None:
        self._session.add(attempt_to_row(attempt))

    def get(self, attempt_id: ValidationAttemptId) -> ValidationAttempt | None:
        row = _database_operation(
            lambda: self._session.get(
                ValidationAttemptRow, _required_id(attempt_id, "attempt_id")
            )
        )
        return None if row is None else attempt_from_row(row)

    def get_by_execution_intent(
        self,
        task_id: VerificationTaskId,
        execution_intent_id: ExecutionIntentId,
    ) -> ValidationAttempt | None:
        statement = select(ValidationAttemptRow).where(
            ValidationAttemptRow.task_id == _required_id(task_id, "task_id"),
            ValidationAttemptRow.execution_intent_id
            == _required_id(execution_intent_id, "execution_intent_id"),
        )
        row = _database_operation(
            lambda: self._session.scalars(statement).one_or_none()
        )
        return None if row is None else attempt_from_row(row)

    def list_executing(self) -> list[ValidationAttempt]:
        statement = (
            select(ValidationAttemptRow)
            .where(
                ValidationAttemptRow.status == ValidationAttemptStatus.EXECUTING.value
            )
            .order_by(
                ValidationAttemptRow.started_at.asc(),
                ValidationAttemptRow.attempt_id.asc(),
            )
        )
        rows = _database_operation(lambda: self._session.scalars(statement).all())
        return [attempt_from_row(row) for row in rows]

    def save(self, attempt: ValidationAttempt) -> None:
        row = _database_operation(
            lambda: self._session.get(
                ValidationAttemptRow,
                _required_id(attempt.attempt_id, "attempt_id"),
            )
        )
        if row is None:
            raise ValidationAttemptNotFound(
                f"Validation attempt {attempt.attempt_id} was not found."
            )
        fixed_bindings = (
            (row.attempt_id, _required_id(attempt.attempt_id, "attempt_id")),
            (row.task_id, _required_id(attempt.task_id, "task_id")),
            (row.attempt_no, attempt.attempt_no),
            (row.plan_id, _required_id(attempt.plan_id, "plan_id")),
            (
                row.openapi_snapshot_id,
                _required_id(attempt.openapi_snapshot_id, "openapi_snapshot_id"),
            ),
            (
                row.execution_intent_id,
                _required_id(attempt.execution_intent_id, "execution_intent_id"),
            ),
            (row.is_rerun, int(attempt.is_rerun)),
            (
                row.previous_attempt_id,
                id_to_database(attempt.previous_attempt_id),
            ),
            (row.created_at, datetime_to_database(attempt.created_at)),
            (row.started_at, datetime_to_database(attempt.started_at)),
        )
        if any(persisted != incoming for persisted, incoming in fixed_bindings):
            raise AttemptStateConflict(
                "Attempt fixed bindings cannot be changed when saving."
            )
        apply_attempt_state_to_row(attempt, row)


class SqlAlchemyEvidenceRepository:
    """Append-only persistence for already-produced evidence records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_bundle(self, record: EvidenceBundleRecord) -> None:
        self._session.add(
            EvidenceBundleRow(
                evidence_bundle_id=_required_id(
                    record.evidence_bundle_id, "evidence_bundle_id"
                ),
                attempt_id=_required_id(record.attempt_id, "attempt_id"),
                task_id=_required_id(record.task_id, "task_id"),
                plan_id=_required_id(record.plan_id, "plan_id"),
                openapi_snapshot_id=_required_id(
                    record.openapi_snapshot_id, "openapi_snapshot_id"
                ),
                evaluation_result_id=_required_id(
                    record.evaluation_result_id, "evaluation_result_id"
                ),
                bundle_format_version=record.bundle_format_version,
                manifest_json=record.manifest_json,
                manifest_sha256=record.manifest_sha256,
                sealed_at=datetime_to_database(record.sealed_at),
            )
        )

    def add_report(self, record: DerivedReportRecord) -> None:
        self._session.add(
            DerivedReportRow(
                report_id=_required_id(record.report_id, "report_id"),
                evidence_bundle_id=_required_id(
                    record.evidence_bundle_id, "evidence_bundle_id"
                ),
                report_version=record.report_version,
                format=record.format,
                renderer_version=record.renderer_version,
                content_text=record.content_text,
                content_sha256=record.content_sha256,
                created_at=datetime_to_database(record.created_at),
            )
        )


def _database_operation[ResultT](operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except IntegrityError as error:
        raise PersistenceConflict(
            "The database rejected a persistence constraint."
        ) from error
    except SQLAlchemyError as error:
        raise PersistenceUnavailable(
            "The database operation could not be completed."
        ) from error


def _required_id(value: str, field_name: str) -> str:
    serialized = id_to_database(value)
    if serialized is None:
        raise ValueError(f"{field_name} is required.")
    return serialized
