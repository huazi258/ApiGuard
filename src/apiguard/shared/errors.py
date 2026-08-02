"""Minimal shared errors for later state machines."""


class DomainError(Exception):
    """Base error for shared domain invariants."""


class IllegalStateTransitionError(DomainError):
    """Raised when a state machine receives an unsupported transition."""

    def __init__(
        self,
        current_state: str,
        requested_action: str,
        target_state: str,
    ) -> None:
        self.current_state = current_state
        self.requested_action = requested_action
        self.target_state = target_state
        super().__init__(
            f"Cannot {requested_action} from {current_state} to {target_state}."
        )
