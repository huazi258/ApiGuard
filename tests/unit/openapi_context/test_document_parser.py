from __future__ import annotations

from hashlib import sha256

import pytest
from pydantic import ValidationError

from apiguard.openapi_context.document_parser import (
    DecodedOpenAPIDocument,
    OpenAPIDocumentError,
    OpenAPIDocumentErrorCode,
    OpenAPIDocumentFormat,
    OpenAPIDocumentParser,
    ParsedOpenAPIDocument,
)
from apiguard.openapi_context.source import (
    OpenAPISourceAttemptOutcome,
    OpenAPISourceKind,
    OpenAPISourceReadAttempt,
    OpenAPISourceReadResult,
)


def source(
    raw_document: bytes,
    declared_content_type: str | None = None,
    *,
    source_kind: OpenAPISourceKind = OpenAPISourceKind.LOCAL_FILE,
    source_display_value: str = "spec.yaml",
) -> OpenAPISourceReadResult:
    return OpenAPISourceReadResult(
        source_kind=source_kind,
        source_display_value=source_display_value,
        raw_document=raw_document,
        size_bytes=len(raw_document),
        content_sha256=sha256(raw_document).hexdigest(),
        declared_content_type=declared_content_type,
        attempts=(
            OpenAPISourceReadAttempt(
                attempt_no=1,
                outcome=OpenAPISourceAttemptOutcome.SUCCEEDED,
                elapsed_ms=0,
                bytes_received=len(raw_document),
            ),
        ),
    )


def assert_error(
    raw_document: bytes,
    code: OpenAPIDocumentErrorCode,
    *,
    declared_content_type: str | None = None,
    document_format: OpenAPIDocumentFormat | None = None,
) -> OpenAPIDocumentError:
    with pytest.raises(OpenAPIDocumentError) as error:
        OpenAPIDocumentParser().parse(source(raw_document, declared_content_type))
    assert error.value.code is code
    assert error.value.document_format is document_format
    return error.value


@pytest.mark.parametrize(
    ("raw_document", "expected_format"),
    [
        (b'{"openapi":"3.1.0"}', OpenAPIDocumentFormat.JSON),
        (b"openapi: '3.1.0'\n", OpenAPIDocumentFormat.YAML),
    ],
)
def test_decodes_and_parses_utf8_documents(
    raw_document: bytes, expected_format: OpenAPIDocumentFormat
) -> None:
    result = OpenAPIDocumentParser().parse(source(raw_document))
    assert result.document_format is expected_format
    assert result.declared_openapi_version == "3.1.0"


def test_decodes_utf8_bom_once() -> None:
    parsed_source = source(b'\xef\xbb\xbf{"openapi":"3.1.0"}')
    decoded = OpenAPIDocumentParser().decode(parsed_source)
    assert decoded.text == '{"openapi":"3.1.0"}'
    assert decoded.encoding == "utf-8"
    assert decoded.had_utf8_bom


@pytest.mark.parametrize(
    "raw_document",
    [
        b"\xff\xfe{\x00}\x00",
        b"\xfe\xff\x00{\x00}",
        b"\xff\xfe\x00\x00{\x00\x00\x00",
        b"\x00\x00\xfe\xff\x00\x00\x00{",
    ],
)
def test_rejects_utf16_and_utf32_boms(raw_document: bytes) -> None:
    assert_error(
        raw_document, OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED
    )


def test_rejects_invalid_utf8_without_exposing_bytes() -> None:
    error = assert_error(
        b"\xff", OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_TEXT_INVALID
    )
    assert "ff" not in error.safe_detail


@pytest.mark.parametrize(
    "declared_content_type",
    [
        None,
        "application/json; charset=utf-8",
        'application/yaml; charset="UTF-8"',
        "application/yaml; charset=utf8",
    ],
)
def test_accepts_utf8_content_type_charsets(
    declared_content_type: str | None,
) -> None:
    result = OpenAPIDocumentParser().parse(
        source(b'{"openapi":"3.1.0"}', declared_content_type)
    )
    assert result.document_format is OpenAPIDocumentFormat.JSON


@pytest.mark.parametrize("charset", ["iso-8859-1", "utf-16", "gbk", "us-ascii"])
def test_rejects_explicit_non_utf8_charset(charset: str) -> None:
    assert_error(
        b'{"openapi":"3.1.0"}',
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED,
        declared_content_type=f"application/json; charset={charset}",
    )


def test_json_nested_data_is_strict_json_and_plain_values() -> None:
    result = OpenAPIDocumentParser().parse(
        source(b'{"openapi":"3.2.0","items":[null,true,1,1.5,{"name":"x"}]}')
    )
    assert result.document_format is OpenAPIDocumentFormat.JSON
    assert result.declared_openapi_version == "3.2.0"
    assert result.root == {
        "openapi": "3.2.0",
        "items": [None, True, 1, 1.5, {"name": "x"}],
    }


@pytest.mark.parametrize(
    "raw_document",
    [
        b'{"openapi":"3.1.0","openapi":"3.0.3"}',
        b'{"info":{"title":"A","title":"B"}}',
    ],
)
def test_json_rejects_duplicate_keys_at_all_levels(raw_document: bytes) -> None:
    assert_error(
        raw_document,
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_DUPLICATE_KEY,
        document_format=OpenAPIDocumentFormat.JSON,
    )


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_json_rejects_non_finite_constants(constant: bytes) -> None:
    assert_error(
        b'{"value":' + constant + b"}",
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
        document_format=OpenAPIDocumentFormat.JSON,
    )


@pytest.mark.parametrize("raw_document", [b"[1,2]", b"true"])
def test_json_rejects_non_object_roots(raw_document: bytes) -> None:
    assert_error(
        raw_document,
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_ROOT_NOT_OBJECT,
        document_format=OpenAPIDocumentFormat.JSON,
    )


def test_json_syntax_failure_falls_back_to_yaml() -> None:
    result = OpenAPIDocumentParser().parse(source(b"openapi: 3.1.0\nitems:\n  - value"))
    assert result.document_format is OpenAPIDocumentFormat.YAML


def test_json_trailing_garbage_is_syntax_invalid() -> None:
    assert_error(
        b'{"openapi":"3.1.0"} trailing',
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_SYNTAX_INVALID,
        document_format=OpenAPIDocumentFormat.YAML,
    )


@pytest.mark.parametrize(
    "raw_document",
    [
        b"openapi: 3.1.0\nopenapi: 3.0.3\n",
        b"info:\n  title: A\n  title: B\n",
    ],
)
def test_yaml_rejects_duplicate_keys_at_all_levels(raw_document: bytes) -> None:
    assert_error(
        raw_document,
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_DUPLICATE_KEY,
        document_format=OpenAPIDocumentFormat.YAML,
    )


@pytest.mark.parametrize(
    "raw_document",
    [
        b"1: value\n",
        b"root:\n  true: value\n",
        b"date: 2026-08-04\n",
        b"binary: !!binary SGVsbG8=\n",
        b"items: !!set\n  ? a\n",
        b"value: !custom something\n",
        b"value: .nan\n",
        b"value: .inf\n",
        b"root: &root\n  self: *root\n",
    ],
)
def test_yaml_rejects_non_json_compatible_values(raw_document: bytes) -> None:
    assert_error(
        raw_document,
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
        document_format=OpenAPIDocumentFormat.YAML,
    )


@pytest.mark.parametrize(
    "raw_document",
    [
        b"- item\n",
        b"# comment only\n",
        b"ordinary text\n",
        b"<html>not an OpenAPI document</html>",
    ],
)
def test_yaml_non_object_roots_are_rejected(raw_document: bytes) -> None:
    assert_error(
        raw_document,
        OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_ROOT_NOT_OBJECT,
        document_format=OpenAPIDocumentFormat.YAML,
    )


def test_yaml_aliases_become_independent_plain_containers() -> None:
    result = OpenAPIDocumentParser().parse(
        source(b"base: &base\n  values:\n    - 1\nother: *base\nvalue: 1.5\n")
    )
    assert result.document_format is OpenAPIDocumentFormat.YAML
    assert type(result.root) is dict
    assert type(result.root["base"]) is dict
    assert type(result.root["base"]["values"]) is list
    assert result.root["base"] == result.root["other"]
    assert result.root["base"] is not result.root["other"]
    assert result.root["value"] == 1.5


@pytest.mark.parametrize(
    ("raw_document", "expected_version"),
    [
        (b'{"openapi":"3.1.0"}', "3.1.0"),
        (b'{"swagger":"2.0"}', None),
        (b'{"openapi":3.1}', None),
        (b'{"openapi":"unknown"}', "unknown"),
    ],
)
def test_extracts_but_does_not_validate_declared_openapi_version(
    raw_document: bytes, expected_version: str | None
) -> None:
    result = OpenAPIDocumentParser().parse(source(raw_document))
    assert result.declared_openapi_version == expected_version


def test_parser_never_mutates_source_result_on_success_or_failure() -> None:
    valid_source = source(b'{"openapi":"3.1.0"}')
    valid_before = valid_source.model_dump()
    OpenAPIDocumentParser().parse(valid_source)
    assert valid_source.model_dump() == valid_before
    invalid_source = source(b"\xff")
    invalid_before = invalid_source.model_dump()
    assert_error_source = invalid_source
    with pytest.raises(OpenAPIDocumentError):
        OpenAPIDocumentParser().parse(assert_error_source)
    assert invalid_source.model_dump() == invalid_before


def test_error_contract_is_safe_and_stable_for_remote_urls() -> None:
    remote_source = source(
        b"\xff",
        source_kind=OpenAPISourceKind.REMOTE_HTTP,
        source_display_value="https://example.test/spec?token=***",
    )
    with pytest.raises(OpenAPIDocumentError) as error:
        OpenAPIDocumentParser().parse(remote_source)
    value = error.value
    assert value.code is OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_TEXT_INVALID
    assert value.source_display_value.endswith("token=***")
    assert "secret" not in value.safe_detail
    assert "UnicodeDecodeError" not in value.safe_detail
    assert str(value) == value.code.value


def test_models_are_frozen_and_reject_extra_fields() -> None:
    decoded = DecodedOpenAPIDocument(text="{}", had_utf8_bom=False)
    with pytest.raises(ValidationError):
        decoded.text = "changed"
    with pytest.raises(ValidationError):
        DecodedOpenAPIDocument.model_validate(
            {"text": "{}", "had_utf8_bom": False, "unexpected": True}
        )
    parsed = ParsedOpenAPIDocument(
        document_format=OpenAPIDocumentFormat.JSON,
        root={},
        declared_openapi_version=None,
    )
    with pytest.raises(ValidationError):
        parsed.document_format = OpenAPIDocumentFormat.YAML
    with pytest.raises(ValidationError):
        ParsedOpenAPIDocument.model_validate(
            {
                "document_format": "JSON",
                "root": {},
                "declared_openapi_version": None,
                "unexpected": True,
            }
        )


def test_document_error_codes_are_the_frozen_six() -> None:
    assert {code.value for code in OpenAPIDocumentErrorCode} == {
        "OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED",
        "OPENAPI_DOCUMENT_TEXT_INVALID",
        "OPENAPI_DOCUMENT_SYNTAX_INVALID",
        "OPENAPI_DOCUMENT_DUPLICATE_KEY",
        "OPENAPI_DOCUMENT_ROOT_NOT_OBJECT",
        "OPENAPI_DOCUMENT_VALUE_UNSUPPORTED",
    }
