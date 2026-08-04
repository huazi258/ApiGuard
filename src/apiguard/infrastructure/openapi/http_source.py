"""Bounded synchronous HTTP OpenAPI source adapter."""

import ssl
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from hashlib import sha256
from threading import Event, Lock
from time import monotonic

import httpx

from apiguard.config import Settings
from apiguard.openapi_context.source import (
    OpenAPISourceAttemptOutcome,
    OpenAPISourceDescriptor,
    OpenAPISourceError,
    OpenAPISourceErrorCode,
    OpenAPISourceKind,
    OpenAPISourceReadAttempt,
    OpenAPISourceReadResult,
    safe_source_display_value,
)

_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_RETRYABLE_STATUS_CODES = {502, 503, 504}
_ACCEPT_HEADER = "application/json, application/yaml, application/x-yaml, */*"


class _RemoteReadFailure(Exception):
    def __init__(
        self,
        code: OpenAPISourceErrorCode,
        *,
        retryable: bool,
        bytes_received: int,
        cause: BaseException | None = None,
    ) -> None:
        self.code = code
        self.retryable = retryable
        self.bytes_received = bytes_received
        self.cause = cause


class _AttemptProgress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._bytes_received = 0
        self._client: httpx.Client | None = None
        self._response: httpx.Response | None = None
        self.cancelled = Event()

    @property
    def bytes_received(self) -> int:
        with self._lock:
            return self._bytes_received

    def add_bytes(self, size: int) -> int:
        with self._lock:
            self._bytes_received += size
            return self._bytes_received

    def set_client(self, client: httpx.Client) -> None:
        with self._lock:
            self._client = client

    def set_response(self, response: httpx.Response) -> None:
        with self._lock:
            self._response = response

    def cancel_and_close(self) -> None:
        self.cancelled.set()
        with self._lock:
            response = self._response
            client = self._client
        if response is not None:
            with suppress(httpx.HTTPError):
                response.close()
        if client is not None:
            with suppress(httpx.HTTPError):
                client.close()


class HttpOpenAPISource:
    """Read a remote OpenAPI document with frozen transport and size budgets."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
        timeout_seconds: float | None = None,
        max_attempts: int | None = None,
        max_bytes: int | None = None,
    ) -> None:
        settings = Settings()
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.openapi_fetch_timeout_seconds
        )
        self._max_attempts = (
            max_attempts
            if max_attempts is not None
            else settings.max_openapi_fetch_attempts
        )
        self._max_bytes = (
            max_bytes if max_bytes is not None else settings.max_openapi_document_bytes
        )
        if self._timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        if not 1 <= self._max_attempts <= 2:
            raise ValueError("max_attempts must be between one and two.")
        if self._max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero.")
        self._client_factory = client_factory or _default_client_factory

    def read(self, descriptor: OpenAPISourceDescriptor) -> OpenAPISourceReadResult:
        if descriptor.kind is not OpenAPISourceKind.REMOTE_HTTP:
            raise self._error(
                OpenAPISourceErrorCode.UNSUPPORTED_OPENAPI_SOURCE,
                descriptor,
                (
                    self._failed_attempt(
                        1,
                        monotonic(),
                        0,
                        OpenAPISourceErrorCode.UNSUPPORTED_OPENAPI_SOURCE,
                        retryable=False,
                    ),
                ),
            )

        attempts: list[OpenAPISourceReadAttempt] = []
        for attempt_no in range(1, self._max_attempts + 1):
            started = monotonic()
            try:
                raw_document, content_type = self._run_attempt(descriptor)
            except _RemoteReadFailure as failure:
                should_retry = failure.retryable and attempt_no < self._max_attempts
                attempts.append(
                    self._failed_attempt(
                        attempt_no,
                        started,
                        failure.bytes_received,
                        failure.code,
                        retryable=should_retry,
                    )
                )
                if should_retry:
                    continue
                error = self._error(failure.code, descriptor, tuple(attempts))
                if failure.cause is not None:
                    raise error from failure.cause
                raise error from None
            attempts.append(
                OpenAPISourceReadAttempt(
                    attempt_no=attempt_no,
                    outcome=OpenAPISourceAttemptOutcome.SUCCEEDED,
                    elapsed_ms=self._elapsed_ms(started),
                    bytes_received=len(raw_document),
                )
            )
            return OpenAPISourceReadResult(
                source_kind=descriptor.kind,
                source_display_value=safe_source_display_value(descriptor),
                raw_document=raw_document,
                size_bytes=len(raw_document),
                content_sha256=sha256(raw_document).hexdigest(),
                declared_content_type=content_type,
                attempts=tuple(attempts),
                diagnostics=("OPENAPI_SOURCE_RETRIED",) if len(attempts) > 1 else (),
            )
        raise AssertionError("A bounded remote source read must return or raise.")

    def _run_attempt(
        self, descriptor: OpenAPISourceDescriptor
    ) -> tuple[bytes, str | None]:
        progress = _AttemptProgress()
        executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="apiguard-openapi-attempt"
        )
        future = executor.submit(self._read_in_worker, descriptor, progress)
        try:
            try:
                return future.result(timeout=self._timeout_seconds)
            except FutureTimeoutError as error:
                progress.cancel_and_close()
                with suppress(_RemoteReadFailure, httpx.HTTPError):
                    future.result()
                raise _RemoteReadFailure(
                    OpenAPISourceErrorCode.OPENAPI_FETCH_TIMEOUT,
                    retryable=True,
                    bytes_received=progress.bytes_received,
                    cause=error,
                ) from error
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

    def _read_in_worker(
        self, descriptor: OpenAPISourceDescriptor, progress: _AttemptProgress
    ) -> tuple[bytes, str | None]:
        response: httpx.Response | None = None
        client: httpx.Client | None = None
        try:
            client = self._client_factory()
            progress.set_client(client)
            self._raise_if_cancelled(progress)
            request = httpx.Request(
                "GET",
                descriptor.location,
                headers={"Accept": _ACCEPT_HEADER},
                extensions={"timeout": httpx.Timeout(self._timeout_seconds).as_dict()},
            )
            response = client.send(
                request,
                stream=True,
                auth=None,
                follow_redirects=False,
            )
            progress.set_response(response)
            self._raise_if_cancelled(progress)
            self._validate_response(response)
            content_length = _content_length(response)
            if content_length is not None and content_length > self._max_bytes:
                raise _RemoteReadFailure(
                    OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE,
                    retryable=False,
                    bytes_received=0,
                )
            chunks: list[bytes] = []
            body: Iterator[bytes] = iter(response.iter_bytes())
            for chunk in body:
                received = progress.add_bytes(len(chunk))
                if received > self._max_bytes:
                    raise _RemoteReadFailure(
                        OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE,
                        retryable=False,
                        bytes_received=received,
                    )
                self._raise_if_cancelled(progress)
                chunks.append(chunk)
            self._raise_if_cancelled(progress)
            raw_document = b"".join(chunks)
            if not raw_document:
                raise _RemoteReadFailure(
                    OpenAPISourceErrorCode.OPENAPI_SOURCE_EMPTY,
                    retryable=False,
                    bytes_received=0,
                )
            return raw_document, response.headers.get("content-type")
        except _RemoteReadFailure:
            raise
        except httpx.InvalidURL as error:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.INVALID_OPENAPI_SOURCE_LOCATION,
                retryable=False,
                bytes_received=progress.bytes_received,
                cause=error,
            ) from error
        except httpx.TimeoutException as error:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_FETCH_TIMEOUT,
                retryable=True,
                bytes_received=progress.bytes_received,
                cause=error,
            ) from error
        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.RemoteProtocolError,
        ) as error:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
                retryable=not _has_ssl_error(error),
                bytes_received=progress.bytes_received,
                cause=error,
            ) from error
        except (httpx.DecodingError, httpx.LocalProtocolError) as error:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED,
                retryable=False,
                bytes_received=progress.bytes_received,
                cause=error,
            ) from error
        except httpx.ProxyError as error:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
                retryable=False,
                bytes_received=progress.bytes_received,
                cause=error,
            ) from error
        except httpx.UnsupportedProtocol as error:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.INVALID_OPENAPI_SOURCE_LOCATION,
                retryable=False,
                bytes_received=progress.bytes_received,
                cause=error,
            ) from error
        except httpx.HTTPError as error:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
                retryable=False,
                bytes_received=progress.bytes_received,
                cause=error,
            ) from error
        finally:
            if response is not None:
                with suppress(httpx.HTTPError):
                    response.close()
            if client is not None:
                with suppress(httpx.HTTPError):
                    client.close()

    def _validate_response(self, response: httpx.Response) -> None:
        if response.status_code in _REDIRECT_STATUS_CODES:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_REDIRECT_NOT_ALLOWED,
                retryable=False,
                bytes_received=0,
            )
        if response.status_code in {401, 403}:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_ACCESS_DENIED,
                retryable=False,
                bytes_received=0,
            )
        if response.status_code in {404, 410}:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_NOT_FOUND,
                retryable=False,
                bytes_received=0,
            )
        if response.status_code in _RETRYABLE_STATUS_CODES:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_UNAVAILABLE,
                retryable=True,
                bytes_received=0,
            )
        if not 200 <= response.status_code <= 299:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_HTTP_ERROR,
                retryable=False,
                bytes_received=0,
            )
        if response.status_code == 204:
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_EMPTY,
                retryable=False,
                bytes_received=0,
            )

    def _raise_if_cancelled(self, progress: _AttemptProgress) -> None:
        if progress.cancelled.is_set():
            raise _RemoteReadFailure(
                OpenAPISourceErrorCode.OPENAPI_FETCH_TIMEOUT,
                retryable=True,
                bytes_received=progress.bytes_received,
            )

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int((monotonic() - started) * 1000))

    def _failed_attempt(
        self,
        attempt_no: int,
        started: float,
        bytes_received: int,
        code: OpenAPISourceErrorCode,
        *,
        retryable: bool,
    ) -> OpenAPISourceReadAttempt:
        return OpenAPISourceReadAttempt(
            attempt_no=attempt_no,
            outcome=(
                OpenAPISourceAttemptOutcome.FAILED_RETRYABLE
                if retryable
                else OpenAPISourceAttemptOutcome.FAILED_FINAL
            ),
            elapsed_ms=self._elapsed_ms(started),
            bytes_received=bytes_received,
            error_code=code,
        )

    def _error(
        self,
        code: OpenAPISourceErrorCode,
        descriptor: OpenAPISourceDescriptor,
        attempts: tuple[OpenAPISourceReadAttempt, ...],
    ) -> OpenAPISourceError:
        return OpenAPISourceError(
            code,
            descriptor,
            attempts,
            retryable=False,
            safe_detail="Remote OpenAPI source could not be read.",
        )


def _default_client_factory() -> httpx.Client:
    return httpx.Client(follow_redirects=False, trust_env=False)


def _content_length(response: httpx.Response) -> int | None:
    value = response.headers.get("content-length")
    if value is None:
        return None
    try:
        length = int(value)
    except ValueError:
        return None
    return length if length >= 0 else None


def _has_ssl_error(error: BaseException) -> bool:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return True
        current = current.__cause__ or current.__context__
    return False
