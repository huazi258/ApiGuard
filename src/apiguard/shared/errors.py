"""Minimal shared errors for later state machines."""


class DomainError(Exception):
    """Base error for shared domain invariants."""


class IllegalStateTransitionError(DomainError):
    """Raised when a state machine receives an unsupported transition."""
