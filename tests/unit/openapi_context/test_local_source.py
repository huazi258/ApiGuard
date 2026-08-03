from hashlib import sha256
from pathlib import Path

import pytest

from apiguard.infrastructure.openapi.local_source import LocalFileOpenAPISource
from apiguard.openapi_context.source import (
    OpenAPISourceDescriptor,
    OpenAPISourceError,
    OpenAPISourceErrorCode,
    OpenAPISourceKind,
)


def descriptor(path: Path) -> OpenAPISourceDescriptor:
    return OpenAPISourceDescriptor(
        kind=OpenAPISourceKind.LOCAL_FILE, location=str(path)
    )


def test_reads_raw_unknown_extension_and_sha(tmp_path: Path) -> None:
    path = tmp_path / "spec.any"
    raw = b"\xef\xbb\xbfopenapi: 3.1.0\r\n"
    path.write_bytes(raw)
    result = LocalFileOpenAPISource().read(descriptor(path))
    assert result.raw_document == raw
    assert result.size_bytes == len(raw)
    assert result.content_sha256 == sha256(raw).hexdigest()
    assert len(result.attempts) == 1


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


def test_rejects_missing_and_directory(tmp_path: Path) -> None:
    source = LocalFileOpenAPISource()
    with pytest.raises(OpenAPISourceError) as missing:
        source.read(descriptor(tmp_path / "missing"))
    assert missing.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_NOT_FOUND
    with pytest.raises(OpenAPISourceError) as directory:
        source.read(descriptor(tmp_path))
    assert directory.value.code is OpenAPISourceErrorCode.OPENAPI_SOURCE_READ_FAILED
