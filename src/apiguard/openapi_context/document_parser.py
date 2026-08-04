"""Strict decoding and parsing of retrieved OpenAPI document bytes."""

import json
import math
from enum import StrEnum
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict

from apiguard.openapi_context.source import OpenAPISourceReadResult

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


class OpenAPIDocumentFormat(StrEnum):
    JSON = "JSON"
    YAML = "YAML"


class OpenAPIDocumentErrorCode(StrEnum):
    OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED = "OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED"
    OPENAPI_DOCUMENT_TEXT_INVALID = "OPENAPI_DOCUMENT_TEXT_INVALID"
    OPENAPI_DOCUMENT_SYNTAX_INVALID = "OPENAPI_DOCUMENT_SYNTAX_INVALID"
    OPENAPI_DOCUMENT_DUPLICATE_KEY = "OPENAPI_DOCUMENT_DUPLICATE_KEY"
    OPENAPI_DOCUMENT_ROOT_NOT_OBJECT = "OPENAPI_DOCUMENT_ROOT_NOT_OBJECT"
    OPENAPI_DOCUMENT_VALUE_UNSUPPORTED = "OPENAPI_DOCUMENT_VALUE_UNSUPPORTED"


class DecodedOpenAPIDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    encoding: Literal["utf-8"] = "utf-8"
    had_utf8_bom: bool


class ParsedOpenAPIDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_format: OpenAPIDocumentFormat
    root: dict[str, JsonValue]
    declared_openapi_version: str | None
    diagnostics: tuple[str, ...] = ()


class OpenAPIDocumentError(Exception):
    def __init__(
        self,
        code: OpenAPIDocumentErrorCode,
        source: OpenAPISourceReadResult,
        document_format: OpenAPIDocumentFormat | None,
    ) -> None:
        self.code = code
        self.source_kind = source.source_kind
        self.source_display_value = source.source_display_value
        self.document_format = document_format
        self.safe_detail = "OpenAPI document could not be parsed."
        super().__init__(code.value)


class _DuplicateKeyError(Exception):
    pass


class _UnsupportedValueError(Exception):
    pass


class _StrictSafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: _StrictSafeLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key_node, value_node in node.value:
        key: object = cast(
            object,
            loader.construct_object(  # type: ignore[reportUnknownMemberType]
                key_node, deep=deep
            ),
        )
        if not isinstance(key, str):
            raise _UnsupportedValueError
        if key in mapping:
            raise _DuplicateKeyError
        mapping[key] = cast(
            object,
            loader.construct_object(  # type: ignore[reportUnknownMemberType]
                value_node, deep=deep
            ),
        )
    return mapping


_StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


class OpenAPIDocumentParser:
    """Convert an immutable source read result into a plain parsed data tree."""

    def decode(self, source: OpenAPISourceReadResult) -> DecodedOpenAPIDocument:
        _validate_charset(source)
        raw = source.raw_document
        if raw.startswith(
            (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff", b"\xff\xfe", b"\xfe\xff")
        ):
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED,
                source,
                None,
            )
        had_utf8_bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw[3:] if had_utf8_bom else raw
            return DecodedOpenAPIDocument(
                text=text.decode("utf-8", errors="strict"),
                had_utf8_bom=had_utf8_bom,
            )
        except UnicodeDecodeError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_TEXT_INVALID, source, None
            ) from error

    def parse(self, source: OpenAPISourceReadResult) -> ParsedOpenAPIDocument:
        decoded = self.decode(source)
        try:
            parsed = json.loads(
                decoded.text,
                object_pairs_hook=_json_mapping,
                parse_constant=_reject_json_constant,
            )
        except _DuplicateKeyError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_DUPLICATE_KEY,
                source,
                OpenAPIDocumentFormat.JSON,
            ) from error
        except _UnsupportedValueError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
                source,
                OpenAPIDocumentFormat.JSON,
            ) from error
        except RecursionError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
                source,
                OpenAPIDocumentFormat.JSON,
            ) from error
        except json.JSONDecodeError:
            return self._parse_yaml(source, decoded.text)
        return self._parsed_result(source, parsed, OpenAPIDocumentFormat.JSON)

    def _parse_yaml(
        self, source: OpenAPISourceReadResult, text: str
    ) -> ParsedOpenAPIDocument:
        try:
            parsed = yaml.load(text, Loader=_StrictSafeLoader)
        except _DuplicateKeyError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_DUPLICATE_KEY,
                source,
                OpenAPIDocumentFormat.YAML,
            ) from error
        except _UnsupportedValueError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
                source,
                OpenAPIDocumentFormat.YAML,
            ) from error
        except yaml.constructor.ConstructorError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
                source,
                OpenAPIDocumentFormat.YAML,
            ) from error
        except (ValueError, OverflowError, RecursionError) as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
                source,
                OpenAPIDocumentFormat.YAML,
            ) from error
        except yaml.YAMLError as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_SYNTAX_INVALID,
                source,
                OpenAPIDocumentFormat.YAML,
            ) from error
        return self._parsed_result(source, parsed, OpenAPIDocumentFormat.YAML)

    def _parsed_result(
        self,
        source: OpenAPISourceReadResult,
        parsed: object,
        document_format: OpenAPIDocumentFormat,
    ) -> ParsedOpenAPIDocument:
        try:
            normalized = _normalize_json_value(parsed, set())
        except (_UnsupportedValueError, RecursionError) as error:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_VALUE_UNSUPPORTED,
                source,
                document_format,
            ) from error
        if not isinstance(normalized, dict):
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_ROOT_NOT_OBJECT,
                source,
                document_format,
            )
        version = normalized.get("openapi")
        return ParsedOpenAPIDocument.model_construct(
            document_format=document_format,
            root=normalized,
            declared_openapi_version=version if isinstance(version, str) else None,
        )


def _validate_charset(source: OpenAPISourceReadResult) -> None:
    content_type = source.declared_content_type
    if content_type is None:
        return
    for parameter in content_type.split(";")[1:]:
        name, separator, value = parameter.partition("=")
        if name.strip().lower() != "charset" or not separator:
            continue
        charset = value.strip().strip('"').strip("'").lower()
        if charset not in {"utf-8", "utf8"}:
            raise _error(
                OpenAPIDocumentErrorCode.OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED,
                source,
                None,
            )


def _json_mapping(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    mapping: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in mapping:
            raise _DuplicateKeyError
        mapping[key] = value
    return mapping


def _reject_json_constant(_: str) -> None:
    raise _UnsupportedValueError


def _normalize_json_value(value: object, active_ids: set[int]) -> JsonValue:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is str:
        return value
    if type(value) is float:
        if math.isfinite(value):
            return value
        raise _UnsupportedValueError
    if type(value) is list:
        return _normalize_list(cast(list[object], value), active_ids)
    if type(value) is dict:
        return _normalize_mapping(cast(dict[object, object], value), active_ids)
    raise _UnsupportedValueError


def _normalize_list(value: list[object], active_ids: set[int]) -> list[JsonValue]:
    identity = id(value)
    if identity in active_ids:
        raise _UnsupportedValueError
    active_ids.add(identity)
    try:
        return [_normalize_json_value(item, active_ids) for item in value]
    finally:
        active_ids.remove(identity)


def _normalize_mapping(
    value: dict[object, object], active_ids: set[int]
) -> dict[str, JsonValue]:
    identity = id(value)
    if identity in active_ids:
        raise _UnsupportedValueError
    active_ids.add(identity)
    try:
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _UnsupportedValueError
            normalized[key] = _normalize_json_value(item, active_ids)
        return normalized
    finally:
        active_ids.remove(identity)


def _error(
    code: OpenAPIDocumentErrorCode,
    source: OpenAPISourceReadResult,
    document_format: OpenAPIDocumentFormat | None,
) -> OpenAPIDocumentError:
    return OpenAPIDocumentError(code, source, document_format)
