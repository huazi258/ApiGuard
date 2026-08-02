"""Tests for explicit persistence primitive conversions."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from apiguard.infrastructure.persistence.values import (
    bool_from_database,
    bool_to_database,
    datetime_from_database,
    datetime_to_database,
    enum_from_database,
    enum_to_database,
    id_from_database,
    id_to_database,
)
from apiguard.shared.enums import VerificationTaskStatus
from apiguard.shared.ids import VerificationTaskId


def test_canonical_uuid_round_trips_to_nominal_id() -> None:
    value = str(uuid4())

    assert id_to_database(VerificationTaskId(value)) == value
    assert id_from_database(value, VerificationTaskId) == VerificationTaskId(value)
    assert id_to_database(None) is None


@pytest.mark.parametrize("value", [str(uuid4()).upper(), str(uuid4()).replace("-", "")])
def test_noncanonical_uuid_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="canonical"):
        id_to_database(value)


def test_aware_datetime_is_normalized_to_fixed_utc_text() -> None:
    value = datetime(2026, 8, 3, 9, 27, 1, 7, tzinfo=timezone(timedelta(hours=8)))

    serialized = datetime_to_database(value)

    assert serialized == "2026-08-03T01:27:01.000007Z"
    assert datetime_from_database(serialized) == datetime(
        2026, 8, 3, 1, 27, 1, 7, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 8, 3, 1, 27),
        "2026-08-03T01:27:00Z",
        "2026-08-03 01:27:00.000000Z",
    ],
)
def test_naive_and_noncanonical_datetime_values_are_rejected(
    value: datetime | str,
) -> None:
    with pytest.raises(ValueError):
        if isinstance(value, datetime):
            datetime_to_database(value)
        else:
            datetime_from_database(value)


def test_enum_and_boolean_conversions_are_strict_and_nullable() -> None:
    assert enum_to_database(VerificationTaskStatus.READY) == "READY"
    assert (
        enum_from_database("READY", VerificationTaskStatus)
        is VerificationTaskStatus.READY
    )
    assert enum_to_database(None) is None
    with pytest.raises(ValueError):
        enum_from_database("ready", VerificationTaskStatus)
    assert bool_to_database(True) == 1
    assert bool_from_database(0) is False
    assert bool_from_database(None) is None
    with pytest.raises(ValueError):
        bool_from_database(2)
