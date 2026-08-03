"""Persistence contracts expressed without infrastructure dependencies."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from apiguard.shared.ids import (
    DerivedReportId,
    EvaluationResultId,
    EvidenceBundleId,
    ExecutionIntentId,
    OpenAPIContextSnapshotId,
    ValidationAttemptId,
    ValidationPlanId,
    VerificationTaskId,
)
from apiguard.tasking.models import ValidationAttempt, VerificationTask


@dataclass(frozen=True, slots=True)
class EvidenceBundleRecord:
    """An already-sealed, persistence-neutral evidence bundle to append."""

    evidence_bundle_id: EvidenceBundleId
    attempt_id: ValidationAttemptId
    task_id: VerificationTaskId
    plan_id: ValidationPlanId
    openapi_snapshot_id: OpenAPIContextSnapshotId
    evaluation_result_id: EvaluationResultId
    bundle_format_version: str
    manifest_json: str
    manifest_sha256: str
    sealed_at: datetime


@dataclass(frozen=True, slots=True)
class DerivedReportRecord:
    """A rendered, persistence-neutral report version to append."""

    report_id: DerivedReportId
    evidence_bundle_id: EvidenceBundleId
    report_version: int
    format: str
    renderer_version: str
    content_text: str
    content_sha256: str
    created_at: datetime


class TaskRepository(Protocol):
    """Persistence operations for the task preparation aggregate."""

    def add(self, task: VerificationTask) -> None: ...

    def get(self, task_id: VerificationTaskId) -> VerificationTask | None: ...

    def save(self, task: VerificationTask) -> None: ...


class AttemptRepository(Protocol):
    """Persistence operations for the execution attempt aggregate."""

    def add(self, attempt: ValidationAttempt) -> None: ...

    def get(self, attempt_id: ValidationAttemptId) -> ValidationAttempt | None: ...

    def get_by_execution_intent(
        self,
        task_id: VerificationTaskId,
        execution_intent_id: ExecutionIntentId,
    ) -> ValidationAttempt | None: ...

    def list_executing(self) -> list[ValidationAttempt]: ...

    def save(self, attempt: ValidationAttempt) -> None: ...


class EvidenceRepository(Protocol):
    """Append-only persistence operations for sealed evidence and reports."""

    def add_bundle(self, record: EvidenceBundleRecord) -> None: ...

    def add_report(self, record: DerivedReportRecord) -> None: ...


class UnitOfWork(Protocol):
    """Transactional boundary for application persistence ports."""

    tasks: TaskRepository
    attempts: AttemptRepository
    evidence: EvidenceRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...
