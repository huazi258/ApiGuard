"""Immutable public data contracts for projected OpenAPI context facts."""

from __future__ import annotations

import math
import re
import warnings
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, cast
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from apiguard.openapi_context.document_parser import OpenAPIDocumentFormat
from apiguard.openapi_context.source import OpenAPISourceKind
from apiguard.shared.enums import HttpMethod
from apiguard.shared.ids import OpenAPIContextSnapshotId
from apiguard.shared.json_pointer import JsonPointer

warnings.filterwarnings(
    "ignore",
    message=(
        'Field name "schema" in ".*" shadows an attribute in parent "_ContextModel"'
    ),
    category=UserWarning,
)

_MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
_VERSION_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.\d+$")
_METHOD_ORDER = {
    HttpMethod.GET: 0,
    HttpMethod.HEAD: 1,
    HttpMethod.POST: 2,
    HttpMethod.PUT: 3,
    HttpMethod.PATCH: 4,
    HttpMethod.DELETE: 5,
}
_PARAMETER_LOCATION_ORDER: dict[ParameterLocation, int] = {}


class _ContextModel(BaseModel):
    """Shared strict, immutable configuration for public context contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class _FrozenJsonObject(Mapping[str, object]):
    """A private immutable mapping used by context JSON-value fields."""

    _items: tuple[tuple[str, object], ...]

    def __getitem__(self, key: str) -> object:
        for item_key, value in self._items:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)


def _freeze_json_value(value: object) -> object:
    return _freeze_json_value_inner(value, set())


def _freeze_json_value_inner(value: object, active_ids: set[int]) -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if math.isfinite(value):
            return value
        raise ValueError("Context JSON values must use finite numbers.")
    if isinstance(value, _FrozenJsonObject):
        return value
    if type(value) is list:
        identity = id(cast(object, value))
        if identity in active_ids:
            raise ValueError("Context JSON values cannot contain cycles.")
        active_ids.add(identity)
        try:
            return tuple(
                _freeze_json_value_inner(item, active_ids)
                for item in cast(list[object], value)
            )
        finally:
            active_ids.remove(identity)
    if type(value) is tuple:
        identity = id(cast(object, value))
        if identity in active_ids:
            raise ValueError("Context JSON values cannot contain cycles.")
        active_ids.add(identity)
        try:
            return tuple(
                _freeze_json_value_inner(item, active_ids)
                for item in cast(tuple[object, ...], value)
            )
        finally:
            active_ids.remove(identity)
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        identity = id(cast(object, value))
        if identity in active_ids:
            raise ValueError("Context JSON values cannot contain cycles.")
        active_ids.add(identity)
        try:
            items: list[tuple[str, object]] = []
            for key, item in mapping.items():
                if type(key) is not str:
                    raise ValueError("Context JSON object keys must be strings.")
                items.append((key, _freeze_json_value_inner(item, active_ids)))
            return _FrozenJsonObject(tuple(items))
        finally:
            active_ids.remove(identity)
    raise ValueError("Context JSON values must be ordinary JSON values.")


def _json_value_to_plain(value: object) -> object:
    if isinstance(value, _FrozenJsonObject):
        return {key: _json_value_to_plain(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_json_value_to_plain(item) for item in cast(tuple[object, ...], value)]
    return value


def _json_value_key(value: object) -> object:
    if isinstance(value, _FrozenJsonObject):
        return (
            "object",
            tuple(sorted((key, _json_value_key(item)) for key, item in value.items())),
        )
    if type(value) is tuple:
        return (
            "array",
            tuple(_json_value_key(item) for item in cast(tuple[object, ...], value)),
        )
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        return ("float", value)
    return ("string", value)


def _to_json_pointer(value: object) -> JsonPointer:
    if isinstance(value, JsonPointer):
        return value
    if type(value) is str:
        return JsonPointer(value)
    raise ValueError("A source pointer must be a JSON Pointer string.")


def _serialize_json_pointer(value: JsonPointer) -> str:
    return str(value)


def _to_snapshot_id(value: str) -> OpenAPIContextSnapshotId:
    return OpenAPIContextSnapshotId(value)


type ContextJsonValue = Annotated[
    object,
    BeforeValidator(_freeze_json_value),
    PlainSerializer(_json_value_to_plain, return_type=object),
]
type SourcePointer = Annotated[
    StrictStr,
    AfterValidator(_to_json_pointer),
    PlainSerializer(_serialize_json_pointer, return_type=str),
]
type SnapshotId = Annotated[StrictStr, AfterValidator(_to_snapshot_id)]
type NonEmptyString = Annotated[StrictStr, Field(min_length=1)]
type Sha256 = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


class SnapshotSourceContext(_ContextModel):
    kind: OpenAPISourceKind
    display_value: NonEmptyString
    declared_content_type: StrictStr | None


class RawDocumentIdentity(_ContextModel):
    content_sha256: Sha256
    size_bytes: StrictInt = Field(ge=1, le=_MAX_DOCUMENT_BYTES)


class OpenAPIVersionFamily(StrEnum):
    OPENAPI_3_0 = "OPENAPI_3_0"
    OPENAPI_3_1 = "OPENAPI_3_1"


class OpenAPIVersion(_ContextModel):
    family: OpenAPIVersionFamily
    exact_version: StrictStr

    @model_validator(mode="after")
    def validate_version(self) -> OpenAPIVersion:
        match = _VERSION_PATTERN.fullmatch(self.exact_version)
        if match is None:
            raise ValueError("OpenAPI versions must have three decimal components.")
        family_by_minor = {
            "0": OpenAPIVersionFamily.OPENAPI_3_0,
            "1": OpenAPIVersionFamily.OPENAPI_3_1,
        }
        if (
            match.group("major") != "3"
            or family_by_minor.get(match.group("minor")) is not self.family
        ):
            raise ValueError("OpenAPI version does not match its version family.")
        return self


class OpenAPIDocumentMetadata(_ContextModel):
    title: NonEmptyString
    api_version: NonEmptyString

    @field_validator("title", "api_version")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Document metadata must not be blank.")
        return value


class OperationKey(_ContextModel):
    path: NonEmptyString
    method: HttpMethod

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            not value.startswith("/")
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Operation paths must be absolute paths without URI parts."
            )
        return value


class OperationScope(_ContextModel):
    selected_operations: tuple[OperationKey, ...]

    @model_validator(mode="after")
    def validate_selected_operations(self) -> OperationScope:
        if not self.selected_operations:
            raise ValueError("Operation scope must select at least one operation.")
        if len(set(self.selected_operations)) != len(self.selected_operations):
            raise ValueError("Operation scope cannot contain duplicate operations.")
        if self.selected_operations != tuple(
            sorted(self.selected_operations, key=_operation_key_sort_key)
        ):
            raise ValueError("Operation scope must use stable operation ordering.")
        return self


class ParameterLocation(StrEnum):
    PATH = "PATH"
    QUERY = "QUERY"
    HEADER = "HEADER"


_PARAMETER_LOCATION_ORDER.update(
    {
        ParameterLocation.PATH: 0,
        ParameterLocation.QUERY: 1,
        ParameterLocation.HEADER: 2,
    }
)


class ParameterDeclaredScope(StrEnum):
    PATH_ITEM = "PATH_ITEM"
    OPERATION = "OPERATION"


class ParameterStyle(StrEnum):
    SIMPLE = "SIMPLE"
    FORM = "FORM"


class SuggestedValueKind(StrEnum):
    EXAMPLE = "EXAMPLE"
    DEFAULT = "DEFAULT"


class ParameterSerializationContext(_ContextModel):
    style: ParameterStyle
    explode: StrictBool
    allow_reserved: Literal[False] = False


class SuggestedValueContext(_ContextModel):
    kind: SuggestedValueKind
    value: ContextJsonValue
    source_pointer: SourcePointer
    authoritative: Literal[False] = False


class JsonMediaTypeMatchKind(StrEnum):
    EXACT_JSON = "EXACT_JSON"
    STRUCTURED_JSON_SUFFIX = "STRUCTURED_JSON_SUFFIX"
    STRUCTURED_JSON_SUFFIX_WILDCARD = "STRUCTURED_JSON_SUFFIX_WILDCARD"


class MediaTypeContext(_ContextModel):
    declared_value: NonEmptyString
    normalized_value: NonEmptyString
    match_kind: JsonMediaTypeMatchKind

    @model_validator(mode="after")
    def validate_json_media_type(self) -> MediaTypeContext:
        declared_base = self.declared_value.split(";", maxsplit=1)[0].strip().lower()
        if (
            self.normalized_value != self.normalized_value.lower()
            or ";" in self.normalized_value
            or declared_base != self.normalized_value
        ):
            raise ValueError("Media type normalization is invalid.")
        if self.match_kind is JsonMediaTypeMatchKind.EXACT_JSON:
            is_valid = self.normalized_value == "application/json"
        elif self.match_kind is JsonMediaTypeMatchKind.STRUCTURED_JSON_SUFFIX:
            is_valid = (
                self.normalized_value.startswith("application/")
                and self.normalized_value.endswith("+json")
                and self.normalized_value != "application/*+json"
            )
        else:
            is_valid = self.normalized_value == "application/*+json"
        if not is_valid:
            raise ValueError("Only supported JSON media types are allowed.")
        return self


class SchemaKind(StrEnum):
    ANY = "ANY"
    OBJECT = "OBJECT"
    ARRAY = "ARRAY"
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    NULL = "NULL"


class AdditionalPropertiesPolicy(StrEnum):
    UNSPECIFIED = "UNSPECIFIED"
    ALLOWED = "ALLOWED"
    FORBIDDEN = "FORBIDDEN"


def _validate_numeric_value(value: object) -> int | float:
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("Numeric bounds must be finite integers or floats.")


type FiniteNumber = Annotated[int | float, BeforeValidator(_validate_numeric_value)]


class StringConstraints(_ContextModel):
    min_length: StrictInt | None
    max_length: StrictInt | None

    @model_validator(mode="after")
    def validate_lengths(self) -> StringConstraints:
        _validate_nonnegative_range(self.min_length, self.max_length, "string length")
        return self


class NumericBound(_ContextModel):
    value: FiniteNumber
    inclusive: StrictBool


class NumericConstraints(_ContextModel):
    minimum: NumericBound | None
    maximum: NumericBound | None

    @model_validator(mode="after")
    def validate_bounds(self) -> NumericConstraints:
        if self.minimum is None or self.maximum is None:
            return self
        if self.minimum.value > self.maximum.value:
            raise ValueError("Numeric minimum cannot exceed maximum.")
        if self.minimum.value == self.maximum.value and not (
            self.minimum.inclusive and self.maximum.inclusive
        ):
            raise ValueError(
                "An equal numeric interval must be inclusive at both ends."
            )
        return self


class ArrayConstraints(_ContextModel):
    items: SchemaContext
    min_items: StrictInt | None
    max_items: StrictInt | None

    @model_validator(mode="after")
    def validate_item_counts(self) -> ArrayConstraints:
        _validate_nonnegative_range(self.min_items, self.max_items, "array item count")
        return self


class SchemaPropertyContext(_ContextModel):
    name: NonEmptyString
    schema: SchemaContext  # type: ignore[reportIncompatibleMethodOverride]


class ObjectConstraints(_ContextModel):
    properties: tuple[SchemaPropertyContext, ...]
    required_properties: tuple[StrictStr, ...]
    additional_properties: AdditionalPropertiesPolicy

    @model_validator(mode="after")
    def validate_properties(self) -> ObjectConstraints:
        names = tuple(property_context.name for property_context in self.properties)
        if names != tuple(sorted(names)):
            raise ValueError("Object properties must be sorted by name.")
        if len(set(names)) != len(names):
            raise ValueError("Object property names must be unique.")
        if self.required_properties != tuple(sorted(set(self.required_properties))):
            raise ValueError("Required property names must be unique and sorted.")
        if not set(self.required_properties).issubset(names):
            raise ValueError("Required properties must be declared properties.")
        return self


class SchemaContext(_ContextModel):
    kind: SchemaKind
    nullable: StrictBool
    description: StrictStr | None
    format: StrictStr | None
    enum_values: tuple[ContextJsonValue, ...]
    default_value: ContextJsonValue | None
    example_value: ContextJsonValue | None
    read_only: StrictBool
    write_only: StrictBool
    string_constraints: StringConstraints | None
    numeric_constraints: NumericConstraints | None
    array_constraints: ArrayConstraints | None
    object_constraints: ObjectConstraints | None
    source_pointer: SourcePointer

    @model_validator(mode="after")
    def validate_schema(self) -> SchemaContext:
        if self.read_only and self.write_only:
            raise ValueError("Schemas cannot be both read-only and write-only.")
        enum_keys = tuple(_json_value_key(value) for value in self.enum_values)
        if len(set(enum_keys)) != len(enum_keys):
            raise ValueError("Schema enum values must be unique.")
        constraints = {
            "string": self.string_constraints,
            "numeric": self.numeric_constraints,
            "array": self.array_constraints,
            "object": self.object_constraints,
        }
        allowed: dict[SchemaKind, set[str]] = {
            SchemaKind.STRING: {"string"},
            SchemaKind.INTEGER: {"numeric"},
            SchemaKind.NUMBER: {"numeric"},
            SchemaKind.ARRAY: {"array"},
            SchemaKind.OBJECT: {"object"},
            SchemaKind.BOOLEAN: set(),
            SchemaKind.NULL: set(),
            SchemaKind.ANY: {"array", "object"},
        }
        present = {name for name, value in constraints.items() if value is not None}
        if not present.issubset(allowed[self.kind]):
            raise ValueError("Schema constraints do not match the schema kind.")
        if self.kind is SchemaKind.ARRAY and self.array_constraints is None:
            raise ValueError("Array schemas require item constraints.")
        return self


class ParameterContext(_ContextModel):
    name: NonEmptyString
    location: ParameterLocation
    required: StrictBool
    description: StrictStr | None
    deprecated: StrictBool
    serialization: ParameterSerializationContext
    schema: SchemaContext  # type: ignore[reportIncompatibleMethodOverride]
    suggested_value: SuggestedValueContext | None
    source_pointer: SourcePointer
    declared_scope: ParameterDeclaredScope

    @model_validator(mode="after")
    def validate_parameter(self) -> ParameterContext:
        expected = {
            ParameterLocation.PATH: (ParameterStyle.SIMPLE, False),
            ParameterLocation.QUERY: (ParameterStyle.FORM, True),
            ParameterLocation.HEADER: (ParameterStyle.SIMPLE, False),
        }[self.location]
        if (self.serialization.style, self.serialization.explode) != expected:
            raise ValueError("Parameter serialization does not match its location.")
        if self.location is ParameterLocation.PATH and not self.required:
            raise ValueError("Path parameters must be required.")
        return self


class JsonContentContext(_ContextModel):
    media_type: MediaTypeContext
    schema: SchemaContext | None  # type: ignore[reportIncompatibleMethodOverride]
    suggested_value: SuggestedValueContext | None
    source_pointer: SourcePointer


class RequestBodyContext(_ContextModel):
    required: StrictBool
    description: StrictStr | None
    json_content: tuple[JsonContentContext, ...]
    ignored_content_types: tuple[NonEmptyString, ...]
    source_pointer: SourcePointer

    @model_validator(mode="after")
    def validate_content(self) -> RequestBodyContext:
        _validate_json_content(self.json_content)
        _validate_sorted_unique_strings(
            self.ignored_content_types, "Ignored content types"
        )
        return self


class ExactStatusCode(_ContextModel):
    kind: Literal["EXACT"] = "EXACT"
    status_code: StrictInt = Field(ge=100, le=599)


class DefaultResponse(_ContextModel):
    kind: Literal["DEFAULT"] = "DEFAULT"
    value: Literal["default"] = "default"


type ResponseSelector = Annotated[
    ExactStatusCode | DefaultResponse,
    Field(discriminator="kind"),
]


class ResponseContext(_ContextModel):
    selector: ResponseSelector
    description: NonEmptyString
    json_content: tuple[JsonContentContext, ...]
    ignored_content_types: tuple[NonEmptyString, ...]
    source_pointer: SourcePointer

    @model_validator(mode="after")
    def validate_content(self) -> ResponseContext:
        _validate_json_content(self.json_content)
        _validate_sorted_unique_strings(
            self.ignored_content_types, "Ignored content types"
        )
        return self


class SecuritySchemeType(StrEnum):
    API_KEY = "API_KEY"
    HTTP = "HTTP"
    OAUTH2 = "OAUTH2"
    OPEN_ID_CONNECT = "OPEN_ID_CONNECT"
    MUTUAL_TLS = "MUTUAL_TLS"


class SecuritySchemeContext(_ContextModel):
    name: NonEmptyString
    scheme_type: SecuritySchemeType
    source_pointer: SourcePointer


class SecurityRequirementContext(_ContextModel):
    scheme: SecuritySchemeContext
    scopes: tuple[StrictStr, ...]

    @model_validator(mode="after")
    def validate_scopes(self) -> SecurityRequirementContext:
        _validate_sorted_unique_strings(self.scopes, "Security scopes")
        return self


class SecurityAlternativeContext(_ContextModel):
    requirements: tuple[SecurityRequirementContext, ...]

    @model_validator(mode="after")
    def validate_requirements(self) -> SecurityAlternativeContext:
        if not self.requirements:
            raise ValueError("Security alternatives require at least one scheme.")
        names = tuple(requirement.scheme.name for requirement in self.requirements)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError("Security requirements must be unique and sorted by name.")
        return self


class EffectiveSecurityContext(_ContextModel):
    authentication_required: StrictBool
    alternatives: tuple[SecurityAlternativeContext, ...]

    @model_validator(mode="after")
    def validate_alternatives(self) -> EffectiveSecurityContext:
        if self.authentication_required != bool(self.alternatives):
            raise ValueError(
                "Security alternatives must match the authentication flag."
            )
        alternative_keys = tuple(
            tuple(
                (requirement.scheme.name, requirement.scopes)
                for requirement in alternative.requirements
            )
            for alternative in self.alternatives
        )
        if alternative_keys != tuple(sorted(alternative_keys)) or len(
            set(alternative_keys)
        ) != len(alternative_keys):
            raise ValueError("Security alternatives must be unique and stably ordered.")
        return self


class ServerVariableContext(_ContextModel):
    name: NonEmptyString
    default_value: NonEmptyString
    allowed_values: tuple[StrictStr, ...]
    description: StrictStr | None

    @model_validator(mode="after")
    def validate_allowed_values(self) -> ServerVariableContext:
        _validate_sorted_unique_strings(self.allowed_values, "Server variable values")
        if self.allowed_values and self.default_value not in self.allowed_values:
            raise ValueError("Server variable defaults must be allowed values.")
        return self


class ServerCandidateContext(_ContextModel):
    url_template: NonEmptyString
    description: StrictStr | None
    variables: tuple[ServerVariableContext, ...]
    authoritative_for_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_variables(self) -> ServerCandidateContext:
        names = tuple(variable.name for variable in self.variables)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError("Server variables must be unique and sorted by name.")
        return self


class DiagnosticSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"


class OpenAPIContextDiagnostic(_ContextModel):
    source_pointer: SourcePointer
    severity: DiagnosticSeverity
    code: NonEmptyString
    safe_detail: NonEmptyString


class ReferenceTargetKind(StrEnum):
    SCHEMA = "SCHEMA"
    PARAMETER = "PARAMETER"
    REQUEST_BODY = "REQUEST_BODY"
    RESPONSE = "RESPONSE"
    SECURITY_SCHEME = "SECURITY_SCHEME"


class ReferenceResolutionRecord(_ContextModel):
    reference_pointer: SourcePointer
    original_reference: NonEmptyString
    canonical_target_pointer: SourcePointer
    target_kind: ReferenceTargetKind
    chain_depth: StrictInt = Field(ge=1, le=32)
    openapi_version_family: OpenAPIVersionFamily
    metadata_override_applied: StrictBool


class OperationContext(_ContextModel):
    key: OperationKey
    source_pointer: SourcePointer
    operation_id: StrictStr | None
    summary: StrictStr | None
    description: StrictStr | None
    parameters: tuple[ParameterContext, ...]
    request_body: RequestBodyContext | None
    responses: tuple[ResponseContext, ...]
    effective_security: EffectiveSecurityContext
    server_candidates: tuple[ServerCandidateContext, ...]
    diagnostics: tuple[OpenAPIContextDiagnostic, ...]

    @model_validator(mode="after")
    def validate_operation(self) -> OperationContext:
        if not self.responses:
            raise ValueError("Operations require at least one response.")
        _validate_parameters(self.key.path, self.parameters)
        selectors = tuple(
            _response_selector_key(response.selector) for response in self.responses
        )
        if selectors != tuple(sorted(selectors)) or len(set(selectors)) != len(
            selectors
        ):
            raise ValueError(
                "Responses must be unique and use stable selector ordering."
            )
        if self.server_candidates != tuple(
            sorted(self.server_candidates, key=_server_candidate_sort_key)
        ):
            raise ValueError("Server candidates must use stable ordering.")
        _validate_diagnostics(self.diagnostics)
        return self


class OpenAPIContextSnapshot(_ContextModel):
    openapi_snapshot_id: SnapshotId
    source: SnapshotSourceContext
    raw_document_identity: RawDocumentIdentity
    document_format: OpenAPIDocumentFormat
    openapi_version: OpenAPIVersion
    document_metadata: OpenAPIDocumentMetadata
    operation_scope: OperationScope
    operations: tuple[OperationContext, ...]
    reference_resolutions: tuple[ReferenceResolutionRecord, ...]
    diagnostics: tuple[OpenAPIContextDiagnostic, ...]

    @model_validator(mode="after")
    def validate_snapshot(self) -> OpenAPIContextSnapshot:
        if not self.operations:
            raise ValueError("OpenAPI context snapshots require operations.")
        keys = tuple(operation.key for operation in self.operations)
        if keys != tuple(sorted(keys, key=_operation_key_sort_key)) or len(
            set(keys)
        ) != len(keys):
            raise ValueError("Snapshot operations must be unique and stably ordered.")
        if self.operation_scope.selected_operations != keys:
            raise ValueError("Operation scope must exactly match snapshot operations.")
        if self.reference_resolutions != tuple(
            sorted(self.reference_resolutions, key=_reference_resolution_sort_key)
        ):
            raise ValueError("Reference resolution records must use stable ordering.")
        _validate_diagnostics(self.diagnostics)
        return self


def _operation_key_sort_key(key: OperationKey) -> tuple[str, int]:
    return (key.path, _METHOD_ORDER[key.method])


def _validate_nonnegative_range(
    minimum: int | None, maximum: int | None, label: str
) -> None:
    if minimum is not None and minimum < 0:
        raise ValueError(f"{label.capitalize()} minimum must be non-negative.")
    if maximum is not None and maximum < 0:
        raise ValueError(f"{label.capitalize()} maximum must be non-negative.")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError(f"{label.capitalize()} minimum cannot exceed maximum.")


def _validate_sorted_unique_strings(values: tuple[str, ...], label: str) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{label} must be unique and sorted.")


def _validate_json_content(values: tuple[JsonContentContext, ...]) -> None:
    normalized_values = tuple(content.media_type.normalized_value for content in values)
    if normalized_values != tuple(sorted(normalized_values)) or len(
        set(normalized_values)
    ) != len(normalized_values):
        raise ValueError("JSON content must be unique and sorted by media type.")


def _response_selector_key(selector: ResponseSelector) -> tuple[int, int]:
    if isinstance(selector, ExactStatusCode):
        return (0, selector.status_code)
    return (1, 0)


def _parameter_sort_key(parameter: ParameterContext) -> tuple[int, str]:
    name = (
        parameter.name.lower()
        if parameter.location is ParameterLocation.HEADER
        else parameter.name
    )
    return (_PARAMETER_LOCATION_ORDER[parameter.location], name)


def _validate_parameters(path: str, parameters: tuple[ParameterContext, ...]) -> None:
    identities = tuple(
        (
            parameter.location,
            parameter.name.lower()
            if parameter.location is ParameterLocation.HEADER
            else parameter.name,
        )
        for parameter in parameters
    )
    if len(set(identities)) != len(identities):
        raise ValueError("Operation parameters must have unique identities.")
    if parameters != tuple(sorted(parameters, key=_parameter_sort_key)):
        raise ValueError("Operation parameters must use stable ordering.")
    reserved_headers = {"accept", "content-type", "authorization"}
    if any(
        parameter.location is ParameterLocation.HEADER
        and parameter.name.lower() in reserved_headers
        for parameter in parameters
    ):
        raise ValueError("Reserved HTTP headers cannot be ordinary parameters.")
    path_names = tuple(re.findall(r"\{([^{}]+)\}", path))
    path_parameters = tuple(
        parameter.name
        for parameter in parameters
        if parameter.location is ParameterLocation.PATH
    )
    if len(set(path_names)) != len(path_names) or tuple(sorted(path_names)) != tuple(
        sorted(path_parameters)
    ):
        raise ValueError("Path parameters must exactly match path placeholders.")


def _validate_diagnostics(values: tuple[OpenAPIContextDiagnostic, ...]) -> None:
    if values != tuple(
        sorted(
            values,
            key=lambda diagnostic: (
                str(diagnostic.source_pointer),
                diagnostic.severity.value,
                diagnostic.code,
            ),
        )
    ):
        raise ValueError("Diagnostics must use stable ordering.")


def _reference_resolution_sort_key(
    record: ReferenceResolutionRecord,
) -> tuple[str, str, str, str]:
    return (
        str(record.reference_pointer),
        str(record.canonical_target_pointer),
        record.target_kind.value,
        record.original_reference,
    )


def _server_candidate_sort_key(
    candidate: ServerCandidateContext,
) -> tuple[str, str, tuple[tuple[str, str, tuple[str, ...], str], ...]]:
    return (
        candidate.url_template,
        candidate.description or "",
        tuple(
            (
                variable.name,
                variable.default_value,
                variable.allowed_values,
                variable.description or "",
            )
            for variable in candidate.variables
        ),
    )


ArrayConstraints.model_rebuild()
SchemaPropertyContext.model_rebuild()
SchemaContext.model_rebuild()
ParameterContext.model_rebuild()
JsonContentContext.model_rebuild()
RequestBodyContext.model_rebuild()
ResponseContext.model_rebuild()
OperationContext.model_rebuild()
OpenAPIContextSnapshot.model_rebuild()
