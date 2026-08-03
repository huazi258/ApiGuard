import pytest
from pydantic import ValidationError

from apiguard.openapi_context.source import OpenAPISourceDescriptor, OpenAPISourceKind


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
    "location",
    [
        "",
        " ",
        "ftp://example.test",
        "https://user:pass@example.test",
        "https://example.test/spec#part",
    ],
)
def test_descriptor_rejects_invalid_locations(location: str) -> None:
    with pytest.raises(ValidationError):
        OpenAPISourceDescriptor(kind=OpenAPISourceKind.REMOTE_HTTP, location=location)
