"""Explicit primitive conversions at the persistence boundary."""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

_UTC_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def id_to_database(value: str | None) -> str | None:
    """Validate and serialize one canonical UUID identifier."""

    if value is None:
        return None
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("Persistence identifiers must be canonical lowercase UUIDs.")
    return value


def id_from_database[IdT: str](
    value: str | None,
    factory: Callable[[str], IdT],
) -> IdT | None:
    """Validate one database UUID and construct its nominal ID type."""

    serialized = id_to_database(value)
    return None if serialized is None else factory(serialized)


def datetime_to_database(value: datetime | None) -> str | None:
    """Serialize aware datetimes as fixed-width UTC RFC3339 text."""

    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Persistence datetimes must be timezone-aware.")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def datetime_from_database(value: str | None) -> datetime | None:
    """Parse only fixed-width UTC RFC3339 text produced by this boundary."""

    if value is None:
        return None
    if _UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "Persistence datetime text must be UTC RFC3339 with six microseconds."
        )
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def enum_to_database(value: StrEnum | None) -> str | None:
    """Serialize a frozen string enum without changing its stable value."""

    return None if value is None else value.value


def enum_from_database[EnumT: StrEnum](
    value: str | None,
    enum_type: type[EnumT],
) -> EnumT | None:
    """Restore a frozen string enum, rejecting unknown persistence values."""

    return None if value is None else enum_type(value)


def bool_to_database(value: bool | None) -> int | None:
    """Represent nullable booleans as SQLite's constrained 0/1 values."""

    return None if value is None else int(value)


def bool_from_database(value: int | None) -> bool | None:
    """Restore nullable SQLite booleans without accepting arbitrary integers."""

    if value is None:
        return None
    if value not in (0, 1):
        raise ValueError("Persistence booleans must be 0 or 1.")
    return bool(value)
