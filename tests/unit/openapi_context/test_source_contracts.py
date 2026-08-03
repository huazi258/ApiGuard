from hashlib import sha256

import pytest
from pydantic import ValidationError

from apiguard.openapi_context.source import (
    OpenAPISourceAttemptOutcome,
    OpenAPISourceDescriptor,
    OpenAPISourceError,
    OpenAPISourceErrorCode,
    OpenAPISourceKind,
    OpenAPISourceReadAttempt,
    OpenAPISourceReadResult,
)


def _attempt(
    attempt_no: int = 1,
    outcome: OpenAPISourceAttemptOutcome = OpenAPISourceAttemptOutcome.SUCCEEDED,
    *,
    bytes_received: int = 2,
    error_code: OpenAPISourceErrorCode | None = None,
) -> OpenAPISourceReadAttempt:
    return OpenAPISourceReadAttempt(
        attempt_no=attempt_no,
        outcome=outcome,
        elapsed_ms=0,
        bytes_received=bytes_received,
        error_code=error_code,
    )


def _result(
    attempts: tuple[OpenAPISourceReadAttempt, ...],
    *,
    content_sha256: str | None = None,
) -> OpenAPISourceReadResult:
    raw_document = b"{}"
    return OpenAPISourceReadResult(
        source_kind=OpenAPISourceKind.LOCAL_FILE,
        source_display_value="spec.yaml",
        raw_document=raw_document,
        size_bytes=len(raw_document),
        content_sha256=content_sha256 or sha256(raw_document).hexdigest(),
        attempts=attempts,
    )


def test_descriptor_validates_without_filesystem_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_exists(_: object) -> bool:
        raise AssertionError("Descriptor must not access the filesystem.")

    monkeypatch.setattr("pathlib.Path.exists", forbidden_exists)
    assert (
        OpenAPISourceDescriptor(
            kind=OpenAPISourceKind.LOCAL_FILE, location="missing.yaml"
        ).location
        == "missing.yaml"
    )
    assert (
        OpenAPISourceDescriptor(
            kind=OpenAPISourceKind.REMOTE_HTTP, location="https://example.test/spec"
        ).kind
        is OpenAPISourceKind.REMOTE_HTTP
    )


@pytest.mark.parametrize(
    ("kind", "location"),
    [
        (OpenAPISourceKind.LOCAL_FILE, "http://example.test/spec"),
        (OpenAPISourceKind.LOCAL_FILE, "https://example.test/spec"),
        (OpenAPISourceKind.LOCAL_FILE, "file:///spec.yaml"),
        (OpenAPISourceKind.LOCAL_FILE, "ftp://example.test/spec"),
        (OpenAPISourceKind.REMOTE_HTTP, "spec.yaml"),
        (OpenAPISourceKind.REMOTE_HTTP, "C:\\spec.yaml"),
        (OpenAPISourceKind.REMOTE_HTTP, ""),
        (OpenAPISourceKind.REMOTE_HTTP, " "),
        (OpenAPISourceKind.REMOTE_HTTP, "ftp://example.test"),
        (OpenAPISourceKind.REMOTE_HTTP, "https://user:pass@example.test"),
        (OpenAPISourceKind.REMOTE_HTTP, "https://example.test/spec#part"),
        (OpenAPISourceKind.REMOTE_HTTP, "https:///spec"),
        (OpenAPISourceKind.LOCAL_FILE, "spec\x00.yaml"),
    ],
)
def test_descriptor_rejects_invalid_kind_and_location_pairs(
    kind: OpenAPISourceKind, location: str
) -> None:
    with pytest.raises(ValidationError):
        OpenAPISourceDescriptor(kind=kind, location=location)


def test_successful_attempt_cannot_have_an_error_code() -> None:
    with pytest.raises(ValidationError):
        _attempt(error_code=OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED)


@pytest.mark.parametrize(
    "outcome",
    [
        OpenAPISourceAttemptOutcome.FAILED_RETRYABLE,
        OpenAPISourceAttemptOutcome.FAILED_FINAL,
    ],
)
def test_failed_attempt_requires_an_error_code(
    outcome: OpenAPISourceAttemptOutcome,
) -> None:
    with pytest.raises(ValidationError):
        _attempt(outcome=outcome)


def test_result_rejects_incorrect_sha256() -> None:
    with pytest.raises(ValidationError):
        _result((_attempt(),), content_sha256="0" * 64)


def test_result_rejects_non_consecutive_attempt_numbers() -> None:
    retry = _attempt(
        2,
        OpenAPISourceAttemptOutcome.FAILED_RETRYABLE,
        error_code=OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
    )
    with pytest.raises(ValidationError):
        _result((retry, _attempt(3)))


def test_result_rejects_non_final_successful_attempt() -> None:
    retry = _attempt(
        2,
        OpenAPISourceAttemptOutcome.FAILED_RETRYABLE,
        error_code=OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
    )
    with pytest.raises(ValidationError):
        _result((_attempt(1), retry, _attempt(3)))


def test_result_rejects_attempt_after_final_failure() -> None:
    final_failure = _attempt(
        1,
        OpenAPISourceAttemptOutcome.FAILED_FINAL,
        error_code=OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED,
    )
    with pytest.raises(ValidationError):
        _result((final_failure, _attempt(2)))


def test_result_allows_retryable_failure_followed_by_success() -> None:
    retry = _attempt(
        1,
        OpenAPISourceAttemptOutcome.FAILED_RETRYABLE,
        bytes_received=0,
        error_code=OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
    )
    result = _result((retry, _attempt(2)))
    assert result.attempts[-1].outcome is OpenAPISourceAttemptOutcome.SUCCEEDED


def test_result_rejects_successful_attempt_with_wrong_byte_count() -> None:
    with pytest.raises(ValidationError):
        _result((_attempt(bytes_received=1),))


def test_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        OpenAPISourceReadAttempt.model_validate(
            {
                "attempt_no": 1,
                "outcome": OpenAPISourceAttemptOutcome.SUCCEEDED,
                "elapsed_ms": 0,
                "bytes_received": 0,
                "unexpected": True,
            }
        )


def test_source_error_exposes_stable_public_fields() -> None:
    descriptor = OpenAPISourceDescriptor(
        kind=OpenAPISourceKind.LOCAL_FILE, location="spec.yaml"
    )
    attempts = (
        _attempt(
            outcome=OpenAPISourceAttemptOutcome.FAILED_FINAL,
            error_code=OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED,
        ),
    )
    error = OpenAPISourceError(
        OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED,
        descriptor,
        attempts,
        retryable=False,
        safe_detail="OpenAPI source could not be read.",
    )
    assert {
        "code",
        "source_kind",
        "source_display_value",
        "retryable",
        "attempts",
        "safe_detail",
    } <= set(vars(error))
