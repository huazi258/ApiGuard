"""End-to-end persistence acceptance for Milestone 2 using Alembic SQLite files."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from apiguard.application.errors import PersistenceConflict
from apiguard.application.ports import EvidenceBundleRecord
from apiguard.infrastructure.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from apiguard.infrastructure.persistence.orm import (
    EvaluationResultRow,
    EvidenceBundleRow,
    VerificationTaskRow,
)
from apiguard.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from apiguard.shared.enums import ValidationConclusion, VerificationTaskStatus
from apiguard.shared.errors import IllegalStateTransitionError
from apiguard.shared.ids import (
    EvaluationResultId,
    EvidenceBundleId,
    OpenAPIContextSnapshotId,
    ValidationPlanId,
    VerificationTaskId,
)
from apiguard.tasking.models import ValidationAttempt, VerificationTask
from tests.integration.persistence.test_repositories import (
    SHA,
    TIME,
    add_task,
    attempt,
    bind_attempt_to_plan,
    identifier,
    seed_plan_snapshot,
    task,
)


def reopen(database_path: Path) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_sqlite_engine(database_path)
    return engine, create_session_factory(engine)


def prepare_ready_task(
    factory: sessionmaker[Session],
) -> tuple[VerificationTask, ValidationPlanId, OpenAPIContextSnapshotId]:
    value = task()
    add_task(factory, value)
    plan_id, snapshot_id = seed_plan_snapshot(factory, value.task_id)
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.tasks.get(value.task_id)
        assert restored is not None
        restored.start_preparation(TIME + timedelta(seconds=1))
        restored.complete_preparation(TIME + timedelta(seconds=2))
        restored.confirm_plan(plan_id, TIME + timedelta(seconds=3))
        uow.tasks.save(restored)
        uow.commit()
    return value, plan_id, snapshot_id


def add_evaluation(
    factory: sessionmaker[Session],
    value: ValidationAttempt,
    plan_id: ValidationPlanId,
    snapshot_id: OpenAPIContextSnapshotId,
) -> EvaluationResultId:
    evaluation_id = identifier(EvaluationResultId)
    with factory() as session:
        session.add(
            EvaluationResultRow(
                evaluation_result_id=evaluation_id,
                attempt_id=value.attempt_id,
                plan_id=plan_id,
                openapi_snapshot_id=snapshot_id,
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
    return evaluation_id


def bundle_record(
    value: ValidationAttempt,
    plan_id: ValidationPlanId,
    snapshot_id: OpenAPIContextSnapshotId,
    evaluation_id: EvaluationResultId,
    task_id: VerificationTaskId,
) -> EvidenceBundleRecord:
    return EvidenceBundleRecord(
        evidence_bundle_id=identifier(EvidenceBundleId),
        attempt_id=value.attempt_id,
        task_id=task_id,
        plan_id=plan_id,
        openapi_snapshot_id=snapshot_id,
        evaluation_result_id=evaluation_id,
        bundle_format_version="v1",
        manifest_json="{}",
        manifest_sha256=SHA,
        sealed_at=TIME + timedelta(seconds=5),
    )


def test_task_recovers_ready_and_cancelled_across_engine_restart(
    migrated_database: Path,
) -> None:
    engine, factory = reopen(migrated_database)
    value, plan_id, _ = prepare_ready_task(factory)
    with factory() as session:
        row = session.get(VerificationTaskRow, value.task_id)
        assert row is not None
        row.original_rule_text = "future rule"
        row.target_base_url = "https://example.test"
        session.commit()
    engine.dispose()

    engine, factory = reopen(migrated_database)
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.tasks.get(value.task_id)
        assert restored is not None
        assert restored.status is VerificationTaskStatus.READY
        assert restored.current_confirmed_plan_id == plan_id
        restored.restart_preparation(TIME + timedelta(seconds=4))
        uow.tasks.save(restored)
        uow.commit()
    with factory() as session:
        row = session.get(VerificationTaskRow, value.task_id)
        assert row is not None
        assert (row.original_rule_text, row.target_base_url) == (
            "future rule",
            "https://example.test",
        )
    cancelled = task()
    add_task(factory, cancelled)
    cancelled_plan_id, _ = seed_plan_snapshot(factory, cancelled.task_id)
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.tasks.get(cancelled.task_id)
        assert restored is not None
        restored.start_preparation(TIME + timedelta(seconds=1))
        restored.complete_preparation(TIME + timedelta(seconds=2))
        restored.confirm_plan(cancelled_plan_id, TIME + timedelta(seconds=3))
        restored.cancel("accepted cancellation", TIME + timedelta(seconds=4))
        uow.tasks.save(restored)
        uow.commit()
    engine.dispose()

    engine, factory = reopen(migrated_database)
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.tasks.get(cancelled.task_id)
        assert restored is not None
        assert restored.status is VerificationTaskStatus.CANCELLED
        assert restored.current_confirmed_plan_id == cancelled_plan_id
    engine.dispose()


def test_attempt_and_atomic_completion_recover_across_engine_restart(
    migrated_database: Path,
) -> None:
    engine, factory = reopen(migrated_database)
    owner, plan_id, snapshot_id = prepare_ready_task(factory)
    value = bind_attempt_to_plan(attempt(owner.task_id), plan_id, snapshot_id)
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.attempts.add(value)
        uow.commit()
    engine.dispose()

    engine, factory = reopen(migrated_database)
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.attempts.get(value.attempt_id)
        assert restored is not None
        assert (
            uow.attempts.get_by_execution_intent(
                owner.task_id, value.execution_intent_id
            )
            is not None
        )
        assert [item.attempt_id for item in uow.attempts.list_executing()] == [
            value.attempt_id
        ]
        restored.record_http_send()
        uow.attempts.save(restored)
        uow.commit()
    evaluation_id = add_evaluation(factory, value, plan_id, snapshot_id)
    bundle = bundle_record(value, plan_id, snapshot_id, evaluation_id, owner.task_id)
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.attempts.get(value.attempt_id)
        assert restored is not None
        restored.complete(
            evaluation_id,
            bundle.evidence_bundle_id,
            ValidationConclusion.PASSED,
            TIME + timedelta(seconds=6),
        )
        uow.attempts.save(restored)
        uow.evidence.add_bundle(bundle)
        uow.commit()
    engine.dispose()

    engine, factory = reopen(migrated_database)
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.attempts.get(value.attempt_id)
        assert restored is not None
        assert restored.actual_send_count == 1
        assert restored.completed_at == TIME + timedelta(seconds=6)
        assert restored.evaluation_result_id == evaluation_id
        assert restored.evidence_bundle_id == bundle.evidence_bundle_id
        assert restored.conclusion is ValidationConclusion.PASSED
        assert uow.attempts.list_executing() == []
        with pytest.raises(IllegalStateTransitionError):
            restored.record_http_send()
    with factory() as session:
        assert session.get(EvidenceBundleRow, bundle.evidence_bundle_id) is not None
    engine.dispose()


def test_failed_final_transaction_leaves_attempt_executing(
    migrated_database: Path,
) -> None:
    engine, factory = reopen(migrated_database)
    owner, plan_id, snapshot_id = prepare_ready_task(factory)
    value = bind_attempt_to_plan(attempt(owner.task_id), plan_id, snapshot_id)
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.attempts.add(value)
        uow.commit()
    evaluation_id = add_evaluation(factory, value, plan_id, snapshot_id)
    invalid = bundle_record(
        value, plan_id, snapshot_id, evaluation_id, identifier(VerificationTaskId)
    )
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.attempts.get(value.attempt_id)
        assert restored is not None
        restored.complete(
            evaluation_id,
            invalid.evidence_bundle_id,
            ValidationConclusion.PASSED,
            TIME + timedelta(seconds=6),
        )
        uow.attempts.save(restored)
        uow.evidence.add_bundle(invalid)
        with pytest.raises(PersistenceConflict):
            uow.commit()
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.attempts.get(value.attempt_id)
        assert restored is not None
        assert restored.completed_at is None
        assert restored.evaluation_result_id is None
        assert restored.evidence_bundle_id is None
        assert restored.conclusion is None
    with factory() as session:
        assert session.scalars(select(EvidenceBundleRow)).all() == []
    engine.dispose()


def test_milestone_2_architecture_boundaries_remain_frozen() -> None:
    production_sources = list(Path("src").rglob("*.py"))
    assert all(
        "create_all(" not in path.read_text(encoding="utf-8")
        for path in production_sources
    )

    startup_source = Path("src/apiguard/main.py").read_text(encoding="utf-8") + Path(
        "src/apiguard/bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "persistence" not in startup_source
    assert "alembic" not in startup_source

    migration_source = next(Path("alembic/versions").glob("*.py")).read_text(
        encoding="utf-8"
    )
    assert "application" not in migration_source
    assert "mappers" not in migration_source
    assert "repositories" not in migration_source

    ports_source = Path("src/apiguard/application/ports.py").read_text(encoding="utf-8")
    assert "sqlalchemy" not in ports_source
    assert "from apiguard.infrastructure" not in ports_source
    assert "fastapi" not in ports_source

    repository_source = Path(
        "src/apiguard/infrastructure/persistence/repositories.py"
    ).read_text(encoding="utf-8")
    assert ".commit(" not in repository_source
    assert ".rollback(" not in repository_source
    assert ".close(" not in repository_source

    reconstitution_callers = [
        path
        for path in production_sources
        if "_reconstitute(" in path.read_text(encoding="utf-8")
        and path.name != "models.py"
    ]
    assert reconstitution_callers == [
        Path("src/apiguard/infrastructure/persistence/mappers.py")
    ]
    assert len(list(Path("alembic/versions").glob("*.py"))) == 1
