from __future__ import annotations

import ssl
from collections.abc import Callable, Iterator
from typing import NotRequired, TypedDict, Unpack

import httpx
import pytest

from apiguard.infrastructure.openapi.http_source import HttpOpenAPISource
from apiguard.openapi_context.source import (
    OpenAPISourceAttemptOutcome,
    OpenAPISourceDescriptor,
    OpenAPISourceError,
    OpenAPISourceErrorCode,
    OpenAPISourceKind,
)

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class RaisingStream(httpx.SyncByteStream):
    def __init__(
        self, chunks: tuple[bytes, ...], error: httpx.HTTPError | None = None
    ) -> None:
        self._chunks = chunks
        self._error = error

    def __iter__(self) -> Iterator[bytes]:
        yield from self._chunks
        if self._error is not None:
            raise self._error

    def close(self) -> None:
        pass


class AdvancingStream(httpx.SyncByteStream):
    def __init__(self, clock: FakeClock, seconds: float) -> None:
        self._clock = clock
        self._seconds = seconds

    def __iter__(self) -> Iterator[bytes]:
        self._clock.advance(self._seconds)
        yield b"x"

    def close(self) -> None:
        pass


class SourceOptions(TypedDict):
    monotonic_clock: NotRequired[Callable[[], float]]
    timeout_seconds: NotRequired[float]
    max_attempts: NotRequired[int]
    max_bytes: NotRequired[int]


def descriptor(
    location: str = "https://example.test/openapi.json",
) -> OpenAPISourceDescriptor:
    return OpenAPISourceDescriptor(
        kind=OpenAPISourceKind.REMOTE_HTTP, location=location
    )


def source_for(
    handler: Callable[[httpx.Request], httpx.Response], **kwargs: Unpack[SourceOptions]
) -> HttpOpenAPISource:
    return HttpOpenAPISource(
        httpx.Client(transport=httpx.MockTransport(handler)), **kwargs
    )


@pytest.mark.parametrize(
    ("content_type", "raw"),
    [
        ("application/json", b'{"openapi":"3.1.0"}'),
        ("application/yaml", b"openapi: 3.1.0\n"),
        ("text/html", b"<html>not parsed</html>"),
        (None, b"no content type"),
        ("application/not-openapi", b"unrecognized type"),
    ],
)
def test_reads_all_2xx_content_types_as_raw_bytes(
    content_type: str | None, raw: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers.get("authorization") is None
        assert request.headers.get("cookie") is None
        headers = {"content-type": content_type} if content_type is not None else {}
        return httpx.Response(200, headers=headers, content=raw)

    result = source_for(handler).read(
        descriptor("https://example.test/spec?token=secret")
    )
    assert result.raw_document == raw
    assert result.declared_content_type == content_type
    assert result.source_display_value == "https://example.test/spec?token=***"
    assert len(result.attempts) == 1
    assert result.attempts[0].outcome is OpenAPISourceAttemptOutcome.SUCCEEDED


def test_never_sends_client_credentials_or_cookies() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") is None
        assert request.headers.get("cookie") is None
        assert request.headers.get("x-api-key") is None
        return httpx.Response(200, content=b"document")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer secret", "X-API-Key": "key"},
        cookies={"session": "secret"},
    )
    HttpOpenAPISource(client).read(descriptor())


@pytest.mark.parametrize("status_code", [204, 200])
def test_rejects_empty_success_bodies_without_retry(status_code: int) -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(status_code, content=b"")

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(descriptor())
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_EMPTY
    assert request_count == 1
    assert error.value.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_FINAL


@pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
def test_rejects_redirects_without_following_location(status_code: int) -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(status_code, headers={"location": "/other"})

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(descriptor())
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_REDIRECT_NOT_ALLOWED
    assert request_count == 1


@pytest.mark.parametrize(
    ("status_code", "code"),
    [
        (401, OpenAPISourceErrorCode.OPENAPI_SOURCE_ACCESS_DENIED),
        (403, OpenAPISourceErrorCode.OPENAPI_SOURCE_ACCESS_DENIED),
        (404, OpenAPISourceErrorCode.OPENAPI_SOURCE_NOT_FOUND),
        (410, OpenAPISourceErrorCode.OPENAPI_SOURCE_NOT_FOUND),
        (429, OpenAPISourceErrorCode.OPENAPI_SOURCE_HTTP_ERROR),
        (500, OpenAPISourceErrorCode.OPENAPI_SOURCE_HTTP_ERROR),
    ],
)
def test_maps_non_retryable_http_errors_once(
    status_code: int, code: OpenAPISourceErrorCode
) -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(status_code, content=b"error body is not retained")

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(descriptor())
    assert error.value.code is code
    assert request_count == 1
    assert not hasattr(error.value, "raw_document")


@pytest.mark.parametrize(
    ("statuses", "expected_code", "expected_attempts"),
    [
        ((503, 200), None, ("FAILED_RETRYABLE", "SUCCEEDED")),
        ((502, 200), None, ("FAILED_RETRYABLE", "SUCCEEDED")),
        (
            (503, 503),
            OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
            ("FAILED_RETRYABLE", "FAILED_FINAL"),
        ),
        (
            (504, 504),
            OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
            ("FAILED_RETRYABLE", "FAILED_FINAL"),
        ),
    ],
)
def test_retries_only_temporary_upstream_statuses(
    statuses: tuple[int, int],
    expected_code: OpenAPISourceErrorCode | None,
    expected_attempts: tuple[str, str],
) -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        status_code = statuses[request_count]
        request_count += 1
        return httpx.Response(status_code, content=b"second complete document")

    source = source_for(handler)
    if expected_code is None:
        result = source.read(descriptor())
        assert result.raw_document == b"second complete document"
        assert result.diagnostics == ("OPENAPI_SOURCE_RETRIED",)
        attempts = result.attempts
    else:
        with pytest.raises(OpenAPISourceError) as error:
            source.read(descriptor())
        assert error.value.code is expected_code
        attempts = error.value.attempts
    assert request_count == 2
    assert tuple(attempt.outcome.value for attempt in attempts) == expected_attempts


@pytest.mark.parametrize("final_timeout", [False, True])
def test_retries_request_timeouts_once(final_timeout: bool) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1 or final_timeout:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, content=b"complete")

    if final_timeout:
        with pytest.raises(OpenAPISourceError) as error:
            source_for(handler).read(descriptor())
        assert error.value.code is OpenAPISourceErrorCode.OPENAPI_FETCH_TIMEOUT
        assert (
            error.value.attempts[-1].outcome is OpenAPISourceAttemptOutcome.FAILED_FINAL
        )
    else:
        result = source_for(handler).read(descriptor())
        assert result.raw_document == b"complete"
    assert request_count == 2


def test_retries_partial_body_interruption_without_concatenating_bytes() -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return httpx.Response(
                200,
                stream=RaisingStream((b'{"openapi":',), httpx.ReadError("interrupted")),
            )
        return httpx.Response(200, content=b'{"openapi":"3.1.0"}')

    result = source_for(handler).read(descriptor())
    assert result.raw_document == b'{"openapi":"3.1.0"}'
    assert result.attempts[0].bytes_received == len(b'{"openapi":')
    assert result.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_RETRYABLE


def test_retries_body_timeout_once() -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return httpx.Response(
                200,
                stream=RaisingStream((), httpx.ReadTimeout("body timed out")),
            )
        return httpx.Response(200, content=b"complete")

    result = source_for(handler).read(descriptor())
    assert result.raw_document == b"complete"
    assert result.attempts[0].error_code is OpenAPISourceErrorCode.OPENAPI_FETCH_TIMEOUT


def test_retries_connect_error_once() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            raise httpx.ConnectError("connect failed", request=request)
        return httpx.Response(200, content=b"complete")

    result = source_for(handler).read(descriptor())
    assert result.raw_document == b"complete"
    assert result.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_RETRYABLE


def test_maps_two_body_interruptions_to_unavailable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=RaisingStream((b"partial",), httpx.ReadError("interrupted")),
        )

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(descriptor())
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE
    assert tuple(attempt.bytes_received for attempt in error.value.attempts) == (7, 7)
    assert tuple(attempt.outcome.value for attempt in error.value.attempts) == (
        "FAILED_RETRYABLE",
        "FAILED_FINAL",
    )


def test_does_not_retry_tls_failure() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        certificate_error = ssl.SSLCertVerificationError("certificate failure")
        raise httpx.ConnectError(
            "connection failed", request=request
        ) from certificate_error

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(descriptor())
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE
    assert error.value.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_FINAL
    assert request_count == 1


def test_deadline_covers_response_body_without_resetting_per_chunk() -> None:
    clock = FakeClock()
    request_count = 0
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        requests.append(request)
        if request_count == 1:
            clock.advance(9)
            return httpx.Response(200, stream=AdvancingStream(clock, 2))
        return httpx.Response(200, content=b"complete")

    result = source_for(handler, monotonic_clock=clock, timeout_seconds=10).read(
        descriptor()
    )
    assert result.raw_document == b"complete"
    assert result.attempts[0].bytes_received == 1
    assert result.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_RETRYABLE
    assert request_count == 2
    assert requests[0].extensions["timeout"]["read"] == 1


def test_rejects_oversized_content_length_without_consuming_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": "5"},
            stream=RaisingStream((), httpx.ReadError("body was consumed")),
        )

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler, max_bytes=4).read(descriptor())
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE
    assert error.value.attempts[0].bytes_received == 0


@pytest.mark.parametrize(
    ("content_length", "content", "should_succeed"),
    [
        (None, b"x" * MAX_DOCUMENT_BYTES, True),
        (None, b"x" * (MAX_DOCUMENT_BYTES + 1), False),
        ("4", b"x" * 5, False),
        ("5", b"x" * 5, False),
    ],
    ids=["exact_limit", "over_limit", "declared_smaller", "declared_equal"],
)
def test_enforces_streamed_decoded_body_limit(
    content_length: str | None, content: bytes, should_succeed: bool
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        headers = (
            {"content-length": content_length} if content_length is not None else {}
        )
        return httpx.Response(200, headers=headers, content=content)

    max_bytes = MAX_DOCUMENT_BYTES if content_length is None else 4
    source = source_for(handler, max_bytes=max_bytes)
    if should_succeed:
        result = source.read(descriptor())
        assert result.raw_document == content
    else:
        with pytest.raises(OpenAPISourceError) as error:
            source.read(descriptor())
        assert error.value.code is OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE
        assert error.value.retryable is False


def test_rejects_non_remote_descriptor_without_sending_request() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("A local descriptor must not reach HTTPX.")

    local = OpenAPISourceDescriptor(
        kind=OpenAPISourceKind.LOCAL_FILE, location="spec.yaml"
    )
    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(local)
    assert error.value.code is OpenAPISourceErrorCode.UNSUPPORTED_OPENAPI_SOURCE


def test_closes_only_an_owned_client() -> None:
    HttpOpenAPISource().close()
    injected_client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200))
    )
    injected = HttpOpenAPISource(injected_client)
    injected.close()
    assert not injected_client.is_closed
    injected_client.close()


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: HttpOpenAPISource(timeout_seconds=0), "timeout_seconds"),
        (lambda: HttpOpenAPISource(max_attempts=0), "max_attempts"),
        (lambda: HttpOpenAPISource(max_attempts=3), "max_attempts"),
        (lambda: HttpOpenAPISource(max_bytes=0), "max_bytes"),
    ],
)
def test_rejects_invalid_constructor_budgets(
    factory: Callable[[], HttpOpenAPISource], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        factory()
