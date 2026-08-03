"""Synchronous SQLAlchemy Unit of Work implementation."""

from types import TracebackType

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from apiguard.application.errors import PersistenceConflict, PersistenceUnavailable
from apiguard.infrastructure.persistence.repositories import (
    SqlAlchemyAttemptRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyTaskRepository,
)


class SqlAlchemyUnitOfWork:
    """Own one session and expose repositories without automatically committing."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session = session_factory()
        self.tasks = SqlAlchemyTaskRepository(self._session)
        self.attempts = SqlAlchemyAttemptRepository(self._session)
        self.evidence = SqlAlchemyEvidenceRepository(self._session)
        self._closed = False

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.rollback()
        finally:
            self.close()

    def commit(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise PersistenceConflict(
                "The database rejected a persistence constraint."
            ) from error
        except OperationalError as error:
            self._session.rollback()
            raise PersistenceUnavailable("The database is unavailable.") from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PersistenceUnavailable(
                "The database operation could not be completed."
            ) from error

    def rollback(self) -> None:
        self._session.rollback()

    def close(self) -> None:
        if not self._closed:
            self._session.close()
            self._closed = True
