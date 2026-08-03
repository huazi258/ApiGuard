from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pytest
from pydantic import ValidationError

from apiguard.infrastructure.openapi.local_source import LocalFileOpenAPISource
from apiguard.openapi_context.source import (
    OpenAPISourceAttemptOutcome,
    OpenAPISourceDescriptor,
    OpenAPISourceError,
    OpenAPISourceErrorCode,
    OpenAPISourceKind,
)

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024


def descriptor(path: Path) -> OpenAPISourceDescriptor:
    return OpenAPISourceDescriptor(
        kind=OpenAPISourceKind.LOCAL_FILE, location=str(path)
    )


@pytest.mark.parametrize(
    ("name", "raw"),
    [
        ("openapi.json", b'{"openapi":"3.1.0"}'),
        ("openapi.yaml", b"openapi: 3.1.0\n"),
        ("spec.any", b"unparsed OpenAPI bytes"),
    ],
)
def test_reads_json_and_yaml_files(tmp_path: Path, name: str, raw: bytes) -> None:
    path = tmp_path / name
    path.write_bytes(raw)
    result = LocalFileOpenAPISource().read(descriptor(path))
    assert result.raw_document == raw
    assert result.size_bytes == len(raw)
    assert result.content_sha256 == sha256(raw).hexdigest()
    attempt = result.attempts[0]
    assert attempt.attempt_no == 1
    assert attempt.outcome is OpenAPISourceAttemptOutcome.SUCCEEDED
    assert attempt.error_code is None
    assert attempt.elapsed_ms >= 0
    assert attempt.bytes_received == len(raw)


def test_reads_exactly_two_mebibytes(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_bytes(b"x" * MAX_DOCUMENT_BYTES)
    result = LocalFileOpenAPISource(max_bytes=MAX_DOCUMENT_BYTES).read(descriptor(path))
    assert result.size_bytes == MAX_DOCUMENT_BYTES


def test_rejects_two_mebibytes_plus_one_byte(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_bytes(b"x" * (MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(OpenAPISourceError) as error:
        LocalFileOpenAPISource(max_bytes=MAX_DOCUMENT_BYTES).read(descriptor(path))
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE
    assert error.value.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_FINAL
    assert not hasattr(error.value, "raw_document")


def test_rejects_file_that_grows_after_size_precheck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "spec.yaml"
    path.write_bytes(b"x")

    class SmallStat:
        st_size = 4

    def exists(_: Path) -> bool:
        return True

    def is_file(_: Path) -> bool:
        return True

    def stat(_: Path) -> SmallStat:
        return SmallStat()

    def open_grown_file(_: Path, *args: object, **kwargs: object) -> BinaryIO:
        return BytesIO(b"x" * 5)

    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(Path, "open", open_grown_file)
    with pytest.raises(OpenAPISourceError) as error:
        LocalFileOpenAPISource(max_bytes=4).read(descriptor(path))
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE
    assert error.value.attempts[0].bytes_received == 5


def test_maps_permission_error_without_platform_file_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "spec.yaml"
    path.write_bytes(b"openapi: 3.1.0\n")

    def denied_open(_: Path, *args: object, **kwargs: object) -> BinaryIO:
        raise PermissionError("private operating system detail")

    monkeypatch.setattr(Path, "open", denied_open)
    with pytest.raises(OpenAPISourceError) as error:
        LocalFileOpenAPISource().read(descriptor(path))
    assert error.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_ACCESS_DENIED
    assert error.value.retryable is False
    assert "private operating system detail" not in error.value.safe_detail
    assert isinstance(error.value.__cause__, PermissionError)


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"", OpenAPISourceErrorCode.OPENAPI_SOURCE_EMPTY),
        (b"x" * 5, OpenAPISourceErrorCode.OPENAPI_DOCUMENT_TOO_LARGE),
    ],
)
def test_rejects_empty_and_oversized_files(
    tmp_path: Path, content: bytes, code: OpenAPISourceErrorCode
) -> None:
    path = tmp_path / "spec"
    path.write_bytes(content)
    with pytest.raises(OpenAPISourceError) as error:
        LocalFileOpenAPISource(max_bytes=4).read(descriptor(path))
    assert error.value.code is code
    assert error.value.attempts[0].outcome is OpenAPISourceAttemptOutcome.FAILED_FINAL
    assert error.value.attempts[0].error_code is code


def test_preserves_relative_source_display_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "spec.yaml").write_bytes(b"openapi: 3.1.0\n")
    monkeypatch.chdir(tmp_path)
    result = LocalFileOpenAPISource().read(descriptor(Path("spec.yaml")))
    assert result.source_display_value == "spec.yaml"


def test_result_is_immutable(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_bytes(b"openapi: 3.1.0\n")
    result = LocalFileOpenAPISource().read(descriptor(path))
    with pytest.raises(ValidationError):
        result.size_bytes = 0


def test_rejects_non_local_descriptor_with_stable_source_error() -> None:
    descriptor = OpenAPISourceDescriptor(
        kind=OpenAPISourceKind.REMOTE_HTTP, location="https://example.test/spec"
    )
    with pytest.raises(OpenAPISourceError) as error:
        LocalFileOpenAPISource().read(descriptor)
    assert error.value.code is OpenAPISourceErrorCode.UNSUPPORTED_OPENAPI_SOURCE
    assert error.value.retryable is False


def test_masks_remote_query_values_in_unsupported_source_error() -> None:
    descriptor = OpenAPISourceDescriptor(
        kind=OpenAPISourceKind.REMOTE_HTTP,
        location="https://example.test/openapi.json?token=secret&tenant=demo",
    )
    with pytest.raises(OpenAPISourceError) as error:
        LocalFileOpenAPISource().read(descriptor)
    assert error.value.code is OpenAPISourceErrorCode.UNSUPPORTED_OPENAPI_SOURCE
    assert error.value.source_display_value == (
        "https://example.test/openapi.json?token=***&tenant=***"
    )
    assert "secret" not in error.value.source_display_value
    assert "demo" not in error.value.source_display_value


@pytest.mark.parametrize("max_bytes", [0, -1])
def test_rejects_non_positive_max_bytes(max_bytes: int) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        LocalFileOpenAPISource(max_bytes=max_bytes)


def test_rejects_missing_and_directory(tmp_path: Path) -> None:
    source = LocalFileOpenAPISource()
    with pytest.raises(OpenAPISourceError) as missing:
        source.read(descriptor(tmp_path / "missing"))
    assert missing.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_NOT_FOUND
    with pytest.raises(OpenAPISourceError) as directory:
        source.read(descriptor(tmp_path))
    assert directory.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED
