"""Tests for Unit of Work database-error containment."""

from typing import cast

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from apiguard.application.errors import PersistenceConflict, PersistenceUnavailable
from apiguard.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class ControlledSession:
    """A minimal session double that triggers one selected SQLAlchemy failure."""

    def __init__(
        self,
        *,
        commit_error: SQLAlchemyError | None = None,
        rollback_error: SQLAlchemyError | None = None,
        close_error: SQLAlchemyError | None = None,
    ) -> None:
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.close_error = close_error
        self.calls: list[str] = []

    def commit(self) -> None:
        self.calls.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self) -> None:
        self.calls.append("rollback")
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self) -> None:
        self.calls.append("close")
        if self.close_error is not None:
            raise self.close_error


def unit_of_work(session: ControlledSession) -> SqlAlchemyUnitOfWork:
    factory = cast(
        sessionmaker[Session],
        lambda: session,
    )
    return SqlAlchemyUnitOfWork(factory)


def test_commit_translates_integrity_error_to_persistence_conflict() -> None:
    session = ControlledSession(
        commit_error=IntegrityError("INSERT", {}, Exception("constraint"))
    )

    with pytest.raises(PersistenceConflict):
        unit_of_work(session).commit()

    assert session.calls == ["commit", "rollback"]


def test_commit_translates_operational_error_to_persistence_unavailable() -> None:
    session = ControlledSession(
        commit_error=OperationalError("COMMIT", {}, Exception("offline"))
    )

    with pytest.raises(PersistenceUnavailable):
        unit_of_work(session).commit()

    assert session.calls == ["commit", "rollback"]


def test_commit_retains_application_error_when_cleanup_rollback_fails() -> None:
    session = ControlledSession(
        commit_error=IntegrityError("INSERT", {}, Exception("constraint")),
        rollback_error=SQLAlchemyError("rollback failed"),
    )

    with pytest.raises(PersistenceConflict):
        unit_of_work(session).commit()

    assert session.calls == ["commit", "rollback"]


def test_direct_rollback_translates_sqlalchemy_error() -> None:
    session = ControlledSession(rollback_error=SQLAlchemyError("rollback failed"))

    with pytest.raises(PersistenceUnavailable):
        unit_of_work(session).rollback()

    assert session.calls == ["rollback"]


def test_direct_close_translates_sqlalchemy_error() -> None:
    session = ControlledSession(close_error=SQLAlchemyError("close failed"))

    with pytest.raises(PersistenceUnavailable):
        unit_of_work(session).close()

    assert session.calls == ["close"]


@pytest.mark.parametrize("failure", ["rollback", "close"])
def test_context_exit_translates_cleanup_failures(failure: str) -> None:
    session = ControlledSession(
        rollback_error=SQLAlchemyError("rollback failed")
        if failure == "rollback"
        else None,
        close_error=SQLAlchemyError("close failed") if failure == "close" else None,
    )

    with pytest.raises(PersistenceUnavailable), unit_of_work(session):
        pass

    assert session.calls == ["rollback", "close"]


def test_normal_commit_rollback_and_context_cleanup_stay_explicit() -> None:
    session = ControlledSession()

    with unit_of_work(session) as uow:
        uow.commit()

    assert session.calls == ["commit", "rollback", "close"]
