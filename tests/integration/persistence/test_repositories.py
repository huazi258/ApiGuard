"""Integration coverage for repositories and Unit of Work on migrated SQLite."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apiguard.application.errors import (
    AttemptStateConflict,
    PersistenceConflict,
    ValidationAttemptNotFound,
    VerificationTaskNotFound,
)
from apiguard.application.ports import DerivedReportRecord, EvidenceBundleRecord
from apiguard.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from apiguard.infrastructure.persistence.orm import (
    DerivedReportRow,
    EvaluationResultRow,
    ModelCallRecordRow,
    NormalizedRuleRow,
    OpenAPISnapshotRow,
    ValidationAttemptRow,
    ValidationPlanSnapshotRow,
    VerificationTaskRow,
)
from apiguard.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from apiguard.shared.enums import (
    ValidationAttemptStatus,
    ValidationConclusion,
    VerificationTaskStatus,
    VerificationTaskType,
)
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

TIME = datetime(2026, 8, 3, 12, tzinfo=UTC)
SHA = "a" * 64


def identifier[IdT: str](factory: Callable[[str], IdT]) -> IdT:
    return factory(str(uuid4()))


@pytest.fixture
def session_factory(
    migrated_database: Path,
) -> Generator[sessionmaker[Session], None, None]:
    engine = create_sqlite_engine(migrated_database)
    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def task(created_at: datetime = TIME) -> VerificationTask:
    return VerificationTask(
        task_id=identifier(VerificationTaskId),
        task_type=VerificationTaskType.BUSINESS_RULE,
        verification_objective="Verify the explicit business rule.",
        created_at=created_at,
    )


def attempt(
    task_id: VerificationTaskId,
    *,
    attempt_no: int = 1,
    execution_intent_id: ExecutionIntentId | None = None,
    started_at: datetime = TIME + timedelta(seconds=1),
) -> ValidationAttempt:
    return ValidationAttempt(
        attempt_id=identifier(ValidationAttemptId),
        task_id=task_id,
        attempt_no=attempt_no,
        plan_id=identifier(ValidationPlanId),
        openapi_snapshot_id=identifier(OpenAPIContextSnapshotId),
        execution_intent_id=execution_intent_id or identifier(ExecutionIntentId),
        is_rerun=False,
        previous_attempt_id=None,
        created_at=TIME,
        started_at=started_at,
    )


def add_task(factory: sessionmaker[Session], value: VerificationTask) -> None:
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.tasks.add(value)
        uow.commit()


def seed_plan_snapshot(
    factory: sessionmaker[Session], task_id: VerificationTaskId
) -> tuple[ValidationPlanId, OpenAPIContextSnapshotId]:
    snapshot_id = identifier(OpenAPIContextSnapshotId)
    model_call_id = str(uuid4())
    rule_id = str(uuid4())
    plan_id = identifier(ValidationPlanId)
    with factory() as session:
        session.add(
            OpenAPISnapshotRow(
                openapi_snapshot_id=snapshot_id,
                task_id=task_id,
                version_no=1,
                source_kind="URL",
                source_display_value="https://example.test/openapi.json",
                openapi_version="3.1.0",
                raw_document="{}",
                raw_size_bytes=2,
                content_sha256=SHA,
                normalized_context_json="{}",
                diagnostics_json="[]",
                created_at="2026-08-03T12:00:00.000000Z",
            )
        )
        session.flush()
        session.add(
            ModelCallRecordRow(
                model_call_id=model_call_id,
                task_id=task_id,
                openapi_snapshot_id=snapshot_id,
                preparation_run_id=str(uuid4()),
                call_sequence=1,
                call_kind="PRIMARY",
                provider_name="test",
                model_name="test-model",
                prompt_version="v1",
                status="SUCCEEDED",
                started_at="2026-08-03T12:00:00.000000Z",
            )
        )
        session.flush()
        session.add(
            NormalizedRuleRow(
                normalized_rule_id=rule_id,
                task_id=task_id,
                openapi_snapshot_id=snapshot_id,
                model_call_id=model_call_id,
                version_no=1,
                original_rule_text="rule",
                normalized_rule_json="{}",
                content_sha256=SHA,
                created_at="2026-08-03T12:00:00.000000Z",
            )
        )
        session.flush()
        session.add(
            ValidationPlanSnapshotRow(
                plan_id=plan_id,
                task_id=task_id,
                normalized_rule_id=rule_id,
                openapi_snapshot_id=snapshot_id,
                version_no=1,
                stage="CONFIRMED",
                plan_json="{}",
                content_sha256=SHA,
                created_at="2026-08-03T12:00:00.000000Z",
            )
        )
        session.commit()
    return plan_id, snapshot_id


def bind_attempt_to_plan(
    value: ValidationAttempt,
    plan_id: ValidationPlanId,
    snapshot_id: OpenAPIContextSnapshotId,
) -> ValidationAttempt:
    return ValidationAttempt(
        attempt_id=value.attempt_id,
        task_id=value.task_id,
        attempt_no=value.attempt_no,
        plan_id=plan_id,
        openapi_snapshot_id=snapshot_id,
        execution_intent_id=value.execution_intent_id,
        is_rerun=value.is_rerun,
        previous_attempt_id=value.previous_attempt_id,
        created_at=value.created_at,
        started_at=value.started_at,
    )


def persisted_attempt(
    factory: sessionmaker[Session],
    task_id: VerificationTaskId,
    *,
    attempt_no: int = 1,
    execution_intent_id: ExecutionIntentId | None = None,
    started_at: datetime = TIME + timedelta(seconds=1),
) -> ValidationAttempt:
    plan_id, snapshot_id = seed_plan_snapshot(factory, task_id)
    value = bind_attempt_to_plan(
        attempt(
            task_id,
            attempt_no=attempt_no,
            execution_intent_id=execution_intent_id,
            started_at=started_at,
        ),
        plan_id,
        snapshot_id,
    )
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.attempts.add(value)
        uow.commit()
    return value


def test_task_repository_add_get_save_and_preserves_future_inputs(
    session_factory: sessionmaker[Session],
) -> None:
    value = task()
    add_task(session_factory, value)
    with session_factory() as session:
        row = session.get(VerificationTaskRow, value.task_id)
        assert row is not None
        row.original_rule_text = "future rule"
        row.target_base_url = "https://example.test"
        row.test_data_json = '{"fixture": true}'
        session.commit()

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        restored = uow.tasks.get(value.task_id)
        assert restored is not None
        restored.start_preparation(TIME + timedelta(seconds=1))
        uow.tasks.save(restored)
        uow.commit()

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        restored = uow.tasks.get(value.task_id)
        assert restored is not None
        assert restored.status is VerificationTaskStatus.PREPARING
    with session_factory() as session:
        row = session.get(VerificationTaskRow, value.task_id)
        assert row is not None
        assert (row.original_rule_text, row.target_base_url, row.test_data_json) == (
            "future rule",
            "https://example.test",
            '{"fixture": true}',
        )


def test_task_repository_missing_and_fixed_fact_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    value = task()
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.tasks.get(value.task_id) is None
        with pytest.raises(VerificationTaskNotFound):
            uow.tasks.save(value)

    add_task(session_factory, value)
    conflicting = VerificationTask(
        task_id=value.task_id,
        task_type=VerificationTaskType.STATE_FLOW,
        verification_objective=value.verification_objective,
        created_at=value.created_at,
    )
    with (
        SqlAlchemyUnitOfWork(session_factory) as uow,
        pytest.raises(PersistenceConflict),
    ):
        uow.tasks.save(conflicting)


def test_attempt_repository_get_queries_saves_and_orders_executing(
    session_factory: sessionmaker[Session],
) -> None:
    first_task = task()
    second_task = task()
    add_task(session_factory, first_task)
    add_task(session_factory, second_task)
    later = persisted_attempt(
        session_factory,
        first_task.task_id,
        started_at=TIME + timedelta(seconds=3),
    )
    earlier = persisted_attempt(
        session_factory,
        second_task.task_id,
        started_at=TIME + timedelta(seconds=2),
    )

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert (
            uow.attempts.get_by_execution_intent(
                first_task.task_id, later.execution_intent_id
            )
            is not None
        )
        assert (
            uow.attempts.get_by_execution_intent(
                first_task.task_id, identifier(ExecutionIntentId)
            )
            is None
        )
        assert uow.attempts.get(identifier(ValidationAttemptId)) is None
        assert [item.attempt_id for item in uow.attempts.list_executing()] == [
            earlier.attempt_id,
            later.attempt_id,
        ]
        restored = uow.attempts.get(later.attempt_id)
        assert restored is not None
        restored.record_http_send()
        uow.attempts.save(restored)
        uow.commit()

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        restored = uow.attempts.get(later.attempt_id)
        assert restored is not None
        assert restored.actual_send_count == 1


def test_attempt_repository_rejects_missing_and_changed_fixed_bindings(
    session_factory: sessionmaker[Session],
) -> None:
    value = attempt(identifier(VerificationTaskId))
    with (
        SqlAlchemyUnitOfWork(session_factory) as uow,
        pytest.raises(ValidationAttemptNotFound),
    ):
        uow.attempts.save(value)

    owner = task()
    add_task(session_factory, owner)
    saved = persisted_attempt(session_factory, owner.task_id)
    changed = ValidationAttempt(
        attempt_id=saved.attempt_id,
        task_id=saved.task_id,
        attempt_no=saved.attempt_no,
        plan_id=saved.plan_id,
        openapi_snapshot_id=saved.openapi_snapshot_id,
        execution_intent_id=identifier(ExecutionIntentId),
        is_rerun=False,
        previous_attempt_id=None,
        created_at=saved.created_at,
        started_at=saved.started_at,
    )
    with (
        SqlAlchemyUnitOfWork(session_factory) as uow,
        pytest.raises(AttemptStateConflict),
    ):
        uow.attempts.save(changed)


def test_unit_of_work_requires_explicit_commit_and_hides_session(
    session_factory: sessionmaker[Session],
) -> None:
    rolled_back = task()
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.tasks.add(rolled_back)
        uow.rollback()
    uncommitted = task()
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.tasks.add(uncommitted)
    exceptional = task()
    with pytest.raises(RuntimeError), SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.tasks.add(exceptional)
        raise RuntimeError("force rollback")

    first = SqlAlchemyUnitOfWork(session_factory)
    second = SqlAlchemyUnitOfWork(session_factory)
    try:
        assert first.tasks is not second.tasks
        assert not hasattr(first, "session")
        assert not hasattr(first.tasks, "commit")
    finally:
        first.close()
        second.close()
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.tasks.get(rolled_back.task_id) is None
        assert uow.tasks.get(uncommitted.task_id) is None
        assert uow.tasks.get(exceptional.task_id) is None


def test_repository_add_does_not_commit_independently(
    session_factory: sessionmaker[Session],
) -> None:
    value = task()
    uow = SqlAlchemyUnitOfWork(session_factory)
    try:
        uow.tasks.add(value)
        with session_factory() as observer:
            assert observer.get(VerificationTaskRow, value.task_id) is None
    finally:
        uow.close()


def test_database_constraint_conflicts_are_application_errors(
    session_factory: sessionmaker[Session],
) -> None:
    value = task()
    add_task(session_factory, value)
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.tasks.add(value)
        with pytest.raises(PersistenceConflict):
            uow.commit()

    owner = task()
    add_task(session_factory, owner)
    first = persisted_attempt(session_factory, owner.task_id)
    second = bind_attempt_to_plan(
        attempt(owner.task_id, attempt_no=2), first.plan_id, first.openapi_snapshot_id
    )
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.attempts.add(second)
        with pytest.raises(PersistenceConflict):
            uow.commit()

    with session_factory() as session:
        row = session.get(ValidationAttemptRow, first.attempt_id)
        assert row is not None
        row.status = ValidationAttemptStatus.COMPLETED.value
        session.commit()
    duplicate_intent = bind_attempt_to_plan(
        attempt(
            owner.task_id,
            attempt_no=2,
            execution_intent_id=first.execution_intent_id,
        ),
        first.plan_id,
        first.openapi_snapshot_id,
    )
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.attempts.add(duplicate_intent)
        with pytest.raises(PersistenceConflict):
            uow.commit()


def test_evidence_repository_is_append_only_and_uses_uow_transactions(
    session_factory: sessionmaker[Session],
) -> None:
    owner = task()
    add_task(session_factory, owner)
    saved = persisted_attempt(session_factory, owner.task_id)
    evaluation_id = identifier(EvaluationResultId)
    with session_factory() as session:
        session.add(
            EvaluationResultRow(
                evaluation_result_id=evaluation_id,
                attempt_id=saved.attempt_id,
                plan_id=saved.plan_id,
                openapi_snapshot_id=saved.openapi_snapshot_id,
                evaluation_input_sha256=SHA,
                assertions_json="[]",
                required_steps_complete=1,
                preconditions_proven=1,
                critical_evidence_missing=0,
                attribution_ambiguous=0,
                conclusion=ValidationConclusion.PASSED.value,
                decision_code="OK",
                decision_detail_json="{}",
                created_at="2026-08-03T12:00:00.000000Z",
            )
        )
        session.commit()
    bundle = EvidenceBundleRecord(
        evidence_bundle_id=identifier(EvidenceBundleId),
        attempt_id=saved.attempt_id,
        task_id=owner.task_id,
        plan_id=saved.plan_id,
        openapi_snapshot_id=saved.openapi_snapshot_id,
        evaluation_result_id=evaluation_id,
        bundle_format_version="v1",
        manifest_json="{}",
        manifest_sha256=SHA,
        sealed_at=TIME,
    )
    report = DerivedReportRecord(
        report_id=identifier(DerivedReportId),
        evidence_bundle_id=bundle.evidence_bundle_id,
        report_version=1,
        format="html",
        renderer_version="v1",
        content_text="report",
        content_sha256=SHA,
        created_at=TIME,
    )
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.evidence.add_bundle(bundle)
        uow.commit()
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.evidence.add_report(report)
        uow.commit()
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.evidence.add_report(
            DerivedReportRecord(
                report_id=identifier(DerivedReportId),
                evidence_bundle_id=bundle.evidence_bundle_id,
                report_version=2,
                format="html",
                renderer_version="v1",
                content_text="discarded",
                content_sha256=SHA,
                created_at=TIME,
            )
        )
        uow.rollback()
    with session_factory() as session:
        assert session.scalars(select(DerivedReportRow)).one().content_text == "report"

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.evidence.add_bundle(bundle)
        with pytest.raises(PersistenceConflict):
            uow.commit()
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.evidence.add_report(
            DerivedReportRecord(
                report_id=identifier(DerivedReportId),
                evidence_bundle_id=bundle.evidence_bundle_id,
                report_version=1,
                format="html",
                renderer_version="v1",
                content_text="duplicate",
                content_sha256=SHA,
                created_at=TIME,
            )
        )
        with pytest.raises(PersistenceConflict):
            uow.commit()
        assert not hasattr(uow.evidence, "update")
        assert not hasattr(uow.evidence, "delete")
