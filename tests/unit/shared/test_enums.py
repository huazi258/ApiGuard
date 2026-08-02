"""Tests for stable shared enumeration values."""

import json
from enum import Enum

import pytest

from apiguard.shared.enums import (
    HttpMethod,
    HttpSendStatus,
    StepExecutionStatus,
    ValidationAttemptStatus,
    ValidationConclusion,
    ValidationPlanStage,
    VerificationTaskStatus,
    VerificationTaskType,
)

EnumType = type[Enum]

EXPECTED_ENUMS: list[tuple[EnumType, dict[str, str]]] = [
    (
        VerificationTaskType,
        {
            "OPENAPI_CONTRACT": "OPENAPI_CONTRACT",
            "BUSINESS_RULE": "BUSINESS_RULE",
            "STATE_FLOW": "STATE_FLOW",
        },
    ),
    (
        VerificationTaskStatus,
        {
            "DRAFT": "DRAFT",
            "PREPARING": "PREPARING",
            "AWAITING_CONFIRMATION": "AWAITING_CONFIRMATION",
            "READY": "READY",
            "CANCELLED": "CANCELLED",
        },
    ),
    (
        ValidationAttemptStatus,
        {"EXECUTING": "EXECUTING", "COMPLETED": "COMPLETED"},
    ),
    (
        ValidationConclusion,
        {
            "PASSED": "PASSED",
            "SUSPECTED_DEFECT": "SUSPECTED_DEFECT",
            "INCONCLUSIVE": "INCONCLUSIVE",
            "EXECUTION_FAILED": "EXECUTION_FAILED",
        },
    ),
    (
        ValidationPlanStage,
        {"CANDIDATE": "CANDIDATE", "VALIDATED": "VALIDATED", "CONFIRMED": "CONFIRMED"},
    ),
    (
        HttpMethod,
        {
            "GET": "GET",
            "HEAD": "HEAD",
            "POST": "POST",
            "PUT": "PUT",
            "PATCH": "PATCH",
            "DELETE": "DELETE",
        },
    ),
    (
        StepExecutionStatus,
        {
            "PENDING": "PENDING",
            "RUNNING": "RUNNING",
            "COMPLETED": "COMPLETED",
            "FAILED": "FAILED",
            "SKIPPED": "SKIPPED",
        },
    ),
    (
        HttpSendStatus,
        {
            "DISPATCHED": "DISPATCHED",
            "RESPONDED": "RESPONDED",
            "FAILED": "FAILED",
            "UNKNOWN_AFTER_INTERRUPT": "UNKNOWN_AFTER_INTERRUPT",
        },
    ),
]


@pytest.mark.parametrize(("enum_type", "expected"), EXPECTED_ENUMS)
def test_members_match_frozen_persistence_values(
    enum_type: EnumType,
    expected: dict[str, str],
) -> None:
    assert {member.name: member.value for member in enum_type} == expected


@pytest.mark.parametrize(("enum_type", "expected"), EXPECTED_ENUMS)
def test_members_serialize_and_restore_stably(
    enum_type: EnumType,
    expected: dict[str, str],
) -> None:
    for value in expected.values():
        member = enum_type(value)

        assert json.dumps(member) == json.dumps(value)
        assert member.value == value


@pytest.mark.parametrize(("enum_type", "expected"), EXPECTED_ENUMS)
def test_invalid_persistence_values_are_rejected(
    enum_type: EnumType,
    expected: dict[str, str],
) -> None:
    del expected

    with pytest.raises(ValueError):
        enum_type("not-a-frozen-value")
