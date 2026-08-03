"""Application-visible errors raised by persistence adapters."""


class PersistenceError(Exception):
    """Base class for persistence failures that may cross the application boundary."""


class VerificationTaskNotFound(PersistenceError):
    """Raised when saving a verification task that has not been persisted."""


class ValidationAttemptNotFound(PersistenceError):
    """Raised when saving a validation attempt that has not been persisted."""


class PersistenceConflict(PersistenceError):
    """Raised when immutable facts or database constraints conflict."""


class TaskStateConflict(PersistenceConflict):
    """Raised when a task's fixed persisted facts would be replaced."""


class AttemptStateConflict(PersistenceConflict):
    """Raised when an attempt's fixed persisted bindings would be replaced."""


class PersistenceUnavailable(PersistenceError):
    """Raised when the database cannot complete an operation."""
