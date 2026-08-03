"""Infrastructure-neutral OpenAPI source contracts."""

from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OpenAPISourceKind(StrEnum):
    LOCAL_FILE = "LOCAL_FILE"
    REMOTE_HTTP = "REMOTE_HTTP"


class OpenAPISourceAttemptOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


class OpenAPISourceErrorCode(StrEnum):
    INVALID_OPENAPI_SOURCE_LOCATION = "INVALID_OPENAPI_SOURCE_LOCATION"
    OPENAPI_SOURCE_NOT_FOUND = "OPENAPI_SOURCE_NOT_FOUND"
    OPENAPI_SOURCE_ACCESS_DENIED = "OPENAPI_SOURCE_ACCESS_DENIED"
    OPENAPI_SOURCE_EMPTY = "OPENAPI_SOURCE_EMPTY"
    OPENAPI_DOCUMENT_TOO_LARGE = "OPENAPI_DOCUMENT_TOO_LARGE"
    OPENAPI_SOURCE_READ_FAILED = "OPENAPI_SOURCE_READ_FAILED"


class OpenAPISourceDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: OpenAPISourceKind
    location: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_location(self) -> "OpenAPISourceDescriptor":
        if not self.location.strip() or "\x00" in self.location:
            raise ValueError("OpenAPI source location must be non-empty and NUL-free.")
        if self.kind is OpenAPISourceKind.REMOTE_HTTP:
            parsed = urlsplit(self.location)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Remote OpenAPI sources require an HTTP(S) URL.")
            if (
                parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
            ):
                raise ValueError(
                    "Remote OpenAPI URLs cannot contain credentials or fragments."
                )
        return self


class OpenAPISourceReadAttempt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    attempt_no: int = Field(ge=1)
    outcome: OpenAPISourceAttemptOutcome
    elapsed_ms: int = Field(ge=0)
    bytes_received: int = Field(ge=0)
    error_code: OpenAPISourceErrorCode | None = None


class OpenAPISourceReadResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_kind: OpenAPISourceKind
    source_display_value: str
    raw_document: bytes = Field(min_length=1)
    size_bytes: int = Field(gt=0, le=2 * 1024 * 1024)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    declared_content_type: str | None = None
    attempts: tuple[OpenAPISourceReadAttempt, ...]
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> "OpenAPISourceReadResult":
        if self.size_bytes != len(self.raw_document):
            raise ValueError("size_bytes must equal raw_document length.")
        if (
            not self.attempts
            or self.attempts[-1].outcome is not OpenAPISourceAttemptOutcome.SUCCEEDED
        ):
            raise ValueError("A successful result requires a final successful attempt.")
        return self


class OpenAPISourceError(Exception):
    def __init__(
        self,
        code: OpenAPISourceErrorCode,
        descriptor: OpenAPISourceDescriptor,
        attempts: tuple[OpenAPISourceReadAttempt, ...],
    ) -> None:
        self.code = code
        self.source_kind = descriptor.kind
        self.source_display_value = descriptor.location
        self.attempts = attempts
        super().__init__(code.value)


class OpenAPISource(Protocol):
    def read(self, descriptor: OpenAPISourceDescriptor) -> OpenAPISourceReadResult: ...
