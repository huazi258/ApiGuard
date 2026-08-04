from __future__ import annotations

import gzip
import ssl
from collections.abc import Callable, Iterator
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from threading import enumerate as enumerate_threads
from time import monotonic, sleep
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


class SourceOptions(TypedDict):
    timeout_seconds: NotRequired[float]
    max_attempts: NotRequired[int]
    max_bytes: NotRequired[int]


class DelayedChunkHandler(BaseHTTPRequestHandler):
    first_chunk_sent: Event
    completed: Event

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        sleep(0.1)
        self.wfile.write(b"first")
        self.wfile.flush()
        self.first_chunk_sent.set()
        sleep(1.0)
        try:
            self.wfile.write(b"second")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.completed.set()

    def log_message(self, format: str, *args: object) -> None:
        pass


class DelayedHeaderHandler(BaseHTTPRequestHandler):
    completed: Event

    def do_GET(self) -> None:  # noqa: N802
        sleep(1.0)
        try:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"late")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.completed.set()

    def log_message(self, format: str, *args: object) -> None:
        pass


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
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        **kwargs,
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
    HttpOpenAPISource(client_factory=lambda: client).read(descriptor())


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


def test_decoding_error_is_not_retried() -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=RaisingStream((b"not a gzip document",)),
        )

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(descriptor())
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED
    assert request_count == 1


def test_local_protocol_error_is_not_retried() -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        raise httpx.LocalProtocolError("invalid local request state")

    with pytest.raises(OpenAPISourceError) as error:
        source_for(handler).read(descriptor())
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED
    assert request_count == 1


def test_remote_protocol_error_is_retried_once() -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            raise httpx.RemoteProtocolError("remote protocol interrupted")
        return httpx.Response(200, content=b"complete")

    result = source_for(handler).read(descriptor())
    assert result.raw_document == b"complete"
    assert result.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_RETRYABLE
    assert request_count == 2


def test_invalid_url_is_a_stable_source_error() -> None:
    with pytest.raises(OpenAPISourceError) as error:
        source_for(lambda _: httpx.Response(200)).read(
            descriptor("https://example.test:notaport/openapi.json")
        )
    assert error.value.code is OpenAPISourceErrorCode.INVALID_OPENAPI_SOURCE_LOCATION
    assert error.value.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_FINAL
    assert len(error.value.attempts) == 1


def test_deadline_interrupts_a_blocking_loopback_body_read() -> None:
    DelayedChunkHandler.first_chunk_sent = Event()
    DelayedChunkHandler.completed = Event()
    server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedChunkHandler)
    server.daemon_threads = True
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()
    try:
        port = server.server_address[1]
        source = HttpOpenAPISource(
            client_factory=lambda: httpx.Client(
                follow_redirects=False, trust_env=False
            ),
            timeout_seconds=0.5,
            max_attempts=1,
        )
        started = monotonic()
        with pytest.raises(OpenAPISourceError) as error:
            source.read(descriptor(f"http://127.0.0.1:{port}/openapi.json"))
        elapsed = monotonic() - started
        assert DelayedChunkHandler.first_chunk_sent.is_set()
        assert error.value.code is OpenAPISourceErrorCode.OPENAPI_FETCH_TIMEOUT
        assert error.value.attempts[0].bytes_received == len(b"first")
        assert elapsed < 0.9
    finally:
        DelayedChunkHandler.completed.wait(timeout=2)
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
    assert not server_thread.is_alive()
    assert not any(
        thread.name.startswith("apiguard-openapi-attempt")
        for thread in enumerate_threads()
    )


def test_deadline_interrupts_a_blocking_loopback_response_header_wait() -> None:
    DelayedHeaderHandler.completed = Event()
    server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedHeaderHandler)
    server.daemon_threads = True
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()
    try:
        port = server.server_address[1]
        source = HttpOpenAPISource(
            client_factory=lambda: httpx.Client(
                follow_redirects=False, trust_env=False
            ),
            timeout_seconds=0.5,
            max_attempts=1,
        )
        started = monotonic()
        with pytest.raises(OpenAPISourceError) as error:
            source.read(descriptor(f"http://127.0.0.1:{port}/openapi.json"))
        assert monotonic() - started < 0.9
        assert error.value.code is OpenAPISourceErrorCode.OPENAPI_FETCH_TIMEOUT
        assert (
            error.value.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_FINAL
        )
        assert error.value.attempts[0].bytes_received == 0
    finally:
        DelayedHeaderHandler.completed.wait(timeout=2)
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
    assert not server_thread.is_alive()
    assert not any(
        thread.name.startswith("apiguard-openapi-attempt")
        for thread in enumerate_threads()
    )


def test_retries_response_header_timeout_with_a_new_client() -> None:
    DelayedHeaderHandler.completed = Event()
    server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedHeaderHandler)
    server.daemon_threads = True
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()
    clients: list[httpx.Client] = []
    try:
        port = server.server_address[1]

        def factory() -> httpx.Client:
            if not clients:
                client = httpx.Client(follow_redirects=False, trust_env=False)
            else:
                client = httpx.Client(
                    transport=httpx.MockTransport(
                        lambda _: httpx.Response(200, content=b"second attempt")
                    )
                )
            clients.append(client)
            return client

        result = HttpOpenAPISource(
            client_factory=factory, timeout_seconds=0.5, max_attempts=2
        ).read(descriptor(f"http://127.0.0.1:{port}/openapi.json"))
        assert result.raw_document == b"second attempt"
        assert tuple(attempt.outcome.value for attempt in result.attempts) == (
            "FAILED_RETRYABLE",
            "SUCCEEDED",
        )
        assert len(clients) == 2
        assert all(client.is_closed for client in clients)
    finally:
        DelayedHeaderHandler.completed.wait(timeout=2)
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
    assert not server_thread.is_alive()


@pytest.mark.parametrize("decoded_size", [512, 513])
def test_enforces_limit_on_gzip_decoded_bytes(decoded_size: int) -> None:
    decoded = b"x" * decoded_size
    compressed = gzip.compress(decoded)
    assert len(compressed) < 512

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=RaisingStream((compressed,)),
        )

    source = source_for(handler, max_bytes=512)
    if decoded_size == 512:
        result = source.read(descriptor())
        assert result.raw_document == decoded
        assert result.size_bytes == decoded_size
        assert result.content_sha256 == sha256(decoded).hexdigest()
    else:
        with pytest.raises(OpenAPISourceError) as error:
            source.read(descriptor())
        assert error.value.code is OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE
        assert error.value.attempts[0].bytes_received == decoded_size
        assert len(error.value.attempts) == 1


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


def test_closes_each_factory_client_after_a_successful_attempt() -> None:
    clients: list[httpx.Client] = []

    def factory() -> httpx.Client:
        client = httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"ok"))
        )
        clients.append(client)
        return client

    result = HttpOpenAPISource(client_factory=factory).read(descriptor())
    assert result.raw_document == b"ok"
    assert len(clients) == 1
    assert clients[0].is_closed


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
