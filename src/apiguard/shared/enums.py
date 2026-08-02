"""Stable persistence enums shared by later ApiGuard modules."""

from enum import StrEnum


class VerificationTaskType(StrEnum):
    OPENAPI_CONTRACT = "OPENAPI_CONTRACT"
    BUSINESS_RULE = "BUSINESS_RULE"
    STATE_FLOW = "STATE_FLOW"


class VerificationTaskStatus(StrEnum):
    DRAFT = "DRAFT"
    PREPARING = "PREPARING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    READY = "READY"
    CANCELLED = "CANCELLED"


class ValidationAttemptStatus(StrEnum):
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"


class ValidationConclusion(StrEnum):
    PASSED = "PASSED"
    SUSPECTED_DEFECT = "SUSPECTED_DEFECT"
    INCONCLUSIVE = "INCONCLUSIVE"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class ValidationPlanStage(StrEnum):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    CONFIRMED = "CONFIRMED"


class HttpMethod(StrEnum):
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class StepExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class HttpSendStatus(StrEnum):
    DISPATCHED = "DISPATCHED"
    RESPONDED = "RESPONDED"
    FAILED = "FAILED"
    UNKNOWN_AFTER_INTERRUPT = "UNKNOWN_AFTER_INTERRUPT"
