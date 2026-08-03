"""Bounded local-file OpenAPI source adapter."""

from hashlib import sha256
from pathlib import Path
from time import monotonic

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


class LocalFileOpenAPISource:
    def __init__(self, max_bytes: int | None = None) -> None:
        self._max_bytes = (
            max_bytes
            if max_bytes is not None
            else Settings().max_openapi_document_bytes
        )
        if self._max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero.")

    def read(self, descriptor: OpenAPISourceDescriptor) -> OpenAPISourceReadResult:
        started = monotonic()
        if descriptor.kind is not OpenAPISourceKind.LOCAL_FILE:
            raise self._error(
                OpenAPISourceErrorCode.UNSUPPORTED_OPENAPI_SOURCE,
                descriptor,
                started,
                0,
            )
        received = 0
        try:
            path = Path(descriptor.location)
            if not path.exists():
                raise self._error(
                    OpenAPISourceErrorCode.OPENAPI_SOURCE_NOT_FOUND,
                    descriptor,
                    started,
                    0,
                )
            if not path.is_file():
                raise self._error(
                    OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED,
                    descriptor,
                    started,
                    0,
                )
            if path.stat().st_size > self._max_bytes:
                raise self._error(
                    OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE,
                    descriptor,
                    started,
                    0,
                )
            chunks: list[bytes] = []
            with path.open("rb") as source:
                while chunk := source.read(
                    min(64 * 1024, self._max_bytes + 1 - received)
                ):
                    received += len(chunk)
                    if received > self._max_bytes:
                        raise self._error(
                            OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE,
                            descriptor,
                            started,
                            received,
                        )
                    chunks.append(chunk)
            raw = b"".join(chunks)
            if not raw:
                raise self._error(
                    OpenAPISourceErrorCode.OPENAPI_SOURCE_EMPTY, descriptor, started, 0
                )
        except OpenAPISourceError:
            raise
        except PermissionError as error:
            raise self._error(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_ACCESS_DENIED,
                descriptor,
                started,
                received,
            ) from error
        except OSError as error:
            raise self._error(
                OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED,
                descriptor,
                started,
                received,
            ) from error
        attempt = OpenAPISourceReadAttempt(
            attempt_no=1,
            outcome=OpenAPISourceAttemptOutcome.SUCCEEDED,
            elapsed_ms=int((monotonic() - started) * 1000),
            bytes_received=received,
        )
        return OpenAPISourceReadResult(
            source_kind=descriptor.kind,
            source_display_value=safe_source_display_value(descriptor),
            raw_document=raw,
            size_bytes=len(raw),
            content_sha256=sha256(raw).hexdigest(),
            attempts=(attempt,),
        )

    def _error(
        self,
        code: OpenAPISourceErrorCode,
        descriptor: OpenAPISourceDescriptor,
        started: float,
        received: int,
    ) -> OpenAPISourceError:
        attempt = OpenAPISourceReadAttempt(
            attempt_no=1,
            outcome=OpenAPISourceAttemptOutcome.FAILED_FINAL,
            elapsed_ms=int((monotonic() - started) * 1000),
            bytes_received=received,
            error_code=code,
        )
        return OpenAPISourceError(
            code,
            descriptor,
            (attempt,),
            retryable=False,
            safe_detail="Local OpenAPI source could not be read.",
        )
