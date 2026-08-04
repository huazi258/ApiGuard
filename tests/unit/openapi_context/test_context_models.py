from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any, cast

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from apiguard.openapi_context.document_parser import OpenAPIDocumentFormat
from apiguard.openapi_context.models import (
    AdditionalPropertiesPolicy,
    ArrayConstraints,
    DefaultResponse,
    DiagnosticSeverity,
    EffectiveSecurityContext,
    ExactStatusCode,
    JsonContentContext,
    JsonMediaTypeMatchKind,
    MediaTypeContext,
    NumericBound,
    NumericConstraints,
    ObjectConstraints,
    OpenAPIContextDiagnostic,
    OpenAPIContextSnapshot,
    OpenAPIDocumentMetadata,
    OpenAPIVersion,
    OpenAPIVersionFamily,
    OperationContext,
    OperationKey,
    OperationScope,
    ParameterContext,
    ParameterDeclaredScope,
    ParameterLocation,
    ParameterSerializationContext,
    ParameterStyle,
    RawDocumentIdentity,
    ReferenceResolutionRecord,
    ReferenceTargetKind,
    RequestBodyContext,
    ResponseContext,
    SchemaContext,
    SchemaKind,
    SchemaPropertyContext,
    SecurityAlternativeContext,
    SecurityRequirementContext,
    SecuritySchemeContext,
    SecuritySchemeType,
    ServerCandidateContext,
    ServerVariableContext,
    SnapshotSourceContext,
    StringConstraints,
    SuggestedValueContext,
    SuggestedValueKind,
)
from apiguard.openapi_context.source import OpenAPISourceKind
from apiguard.shared.enums import HttpMethod
from apiguard.shared.ids import OpenAPIContextSnapshotId
from apiguard.shared.json_pointer import JsonPointer


def schema_context(**overrides: object) -> SchemaContext:
    values: dict[str, object] = {
        "kind": SchemaKind.STRING,
        "nullable": False,
        "description": None,
        "format": None,
        "enum_values": (),
        "default_value": None,
        "example_value": None,
        "read_only": False,
        "write_only": False,
        "string_constraints": None,
        "numeric_constraints": None,
        "array_constraints": None,
        "object_constraints": None,
        "source_pointer": "/components/schemas/Item",
    }
    values.update(overrides)
    return SchemaContext.model_validate(values)


def media_type_context(
    normalized_value: str = "application/json",
    match_kind: JsonMediaTypeMatchKind = JsonMediaTypeMatchKind.EXACT_JSON,
) -> MediaTypeContext:
    return MediaTypeContext(
        declared_value=normalized_value,
        normalized_value=normalized_value,
        match_kind=match_kind,
    )


def suggested_value() -> SuggestedValueContext:
    return SuggestedValueContext(
        kind=SuggestedValueKind.EXAMPLE,
        value={"items": [1, {"enabled": True}]},
        source_pointer="/paths/~1items/get/parameters/0/example",
    )


def json_content() -> JsonContentContext:
    return JsonContentContext(
        media_type=media_type_context(),
        schema=schema_context(),
        suggested_value=suggested_value(),
        source_pointer="/paths/~1items/get/responses/200/content/application~1json",
    )


def response_context(
    selector: ExactStatusCode | DefaultResponse | None = None,
) -> ResponseContext:
    return ResponseContext(
        selector=selector or ExactStatusCode(status_code=200),
        description="Success",
        json_content=(json_content(),),
        ignored_content_types=("text/plain",),
        source_pointer="/paths/~1items/get/responses/200",
    )


def effective_security() -> EffectiveSecurityContext:
    return EffectiveSecurityContext(authentication_required=False, alternatives=())


def operation_context(
    key: OperationKey | None = None,
    **overrides: object,
) -> OperationContext:
    values: dict[str, object] = {
        "key": key or OperationKey(path="/items/{item_id}", method=HttpMethod.GET),
        "source_pointer": "/paths/~1items~1{item_id}/get",
        "operation_id": "getItem",
        "summary": "Get an item",
        "description": None,
        "parameters": (
            ParameterContext(
                name="item_id",
                location=ParameterLocation.PATH,
                required=True,
                description=None,
                deprecated=False,
                serialization=ParameterSerializationContext(
                    style=ParameterStyle.SIMPLE,
                    explode=False,
                ),
                schema=schema_context(),
                suggested_value=None,
                source_pointer="/paths/~1items~1{item_id}/parameters/0",
                declared_scope=ParameterDeclaredScope.PATH_ITEM,
            ),
        ),
        "request_body": None,
        "responses": (response_context(),),
        "effective_security": effective_security(),
        "server_candidates": (),
        "diagnostics": (),
    }
    values.update(overrides)
    return OperationContext.model_validate(values)


def snapshot(version: str = "3.1.0") -> OpenAPIContextSnapshot:
    family = (
        OpenAPIVersionFamily.OPENAPI_3_0
        if version.startswith("3.0.")
        else OpenAPIVersionFamily.OPENAPI_3_1
    )
    operation = operation_context()
    return OpenAPIContextSnapshot(
        openapi_snapshot_id=OpenAPIContextSnapshotId("snapshot-1"),
        source=SnapshotSourceContext(
            kind=OpenAPISourceKind.LOCAL_FILE,
            display_value="fixtures/items.yaml",
            declared_content_type="application/yaml",
        ),
        raw_document_identity=RawDocumentIdentity(
            content_sha256=sha256(b"openapi").hexdigest(),
            size_bytes=7,
        ),
        document_format=OpenAPIDocumentFormat.YAML,
        openapi_version=OpenAPIVersion(family=family, exact_version=version),
        document_metadata=OpenAPIDocumentMetadata(
            title="Items API", api_version="2026.08"
        ),
        operation_scope=OperationScope(selected_operations=(operation.key,)),
        operations=(operation,),
        reference_resolutions=(),
        diagnostics=(),
    )


def assert_invalid(model_type: type[Any], **values: object) -> None:
    with pytest.raises(ValidationError):
        model_type(**values)


def test_frozen_enums_have_only_the_contract_values() -> None:
    assert {member.value for member in OpenAPIVersionFamily} == {
        "OPENAPI_3_0",
        "OPENAPI_3_1",
    }
    assert {member.value for member in ParameterLocation} == {"PATH", "QUERY", "HEADER"}
    assert {member.value for member in ParameterDeclaredScope} == {
        "PATH_ITEM",
        "OPERATION",
    }
    assert {member.value for member in ParameterStyle} == {"SIMPLE", "FORM"}
    assert {member.value for member in SuggestedValueKind} == {"EXAMPLE", "DEFAULT"}
    assert {member.value for member in JsonMediaTypeMatchKind} == {
        "EXACT_JSON",
        "STRUCTURED_JSON_SUFFIX",
        "STRUCTURED_JSON_SUFFIX_WILDCARD",
    }
    assert {member.value for member in SchemaKind} == {
        "ANY",
        "OBJECT",
        "ARRAY",
        "STRING",
        "INTEGER",
        "NUMBER",
        "BOOLEAN",
        "NULL",
    }
    assert {member.value for member in AdditionalPropertiesPolicy} == {
        "UNSPECIFIED",
        "ALLOWED",
        "FORBIDDEN",
    }
    assert {member.value for member in SecuritySchemeType} == {
        "API_KEY",
        "HTTP",
        "OAUTH2",
        "OPEN_ID_CONNECT",
        "MUTUAL_TLS",
    }
    assert {member.value for member in DiagnosticSeverity} == {"INFO", "WARNING"}
    assert {member.value for member in ReferenceTargetKind} == {
        "SCHEMA",
        "PARAMETER",
        "REQUEST_BODY",
        "RESPONSE",
        "SECURITY_SCHEME",
    }


@pytest.mark.parametrize("version", ["3.0.3", "3.1.0"])
def test_manual_snapshots_round_trip_as_plain_json(version: str) -> None:
    original = snapshot(version)
    dumped = original.model_dump(mode="json")
    assert dumped["openapi_snapshot_id"] == "snapshot-1"
    assert dumped["operations"][0]["key"]["method"] == "GET"
    assert dumped["operations"][0]["source_pointer"].startswith("/")
    assert OpenAPIContextSnapshot.model_validate(dumped) == original
    assert (
        OpenAPIContextSnapshot.model_validate_json(original.model_dump_json())
        == original
    )
    assert isinstance(original.operations[0].source_pointer, JsonPointer)
    assert isinstance(original.operations[0].parameters, tuple)


def test_models_reject_extra_fields_and_are_deeply_immutable() -> None:
    original_values: dict[str, object] = {"nested": ["value"]}
    value = SuggestedValueContext(
        kind=SuggestedValueKind.DEFAULT,
        value=original_values,
        source_pointer="/components/schemas/Item/default",
    )
    cast(list[str], original_values["nested"]).append("changed")
    original_values["later"] = True
    assert value.model_dump(mode="json")["value"] == {"nested": ["value"]}
    assert_invalid(
        SnapshotSourceContext,
        kind=OpenAPISourceKind.LOCAL_FILE,
        display_value="spec.yaml",
        declared_content_type=None,
        credential="secret",
    )
    with pytest.raises(ValidationError):
        value.kind = SuggestedValueKind.EXAMPLE
    frozen_nested = cast(Mapping[str, object], value.value)["nested"]
    assert cast(tuple[object, ...], frozen_nested) == ("value",)
    assert not hasattr(frozen_nested, "append")
    with pytest.raises(ValidationError):
        snapshot().source.display_value = "changed"


def test_context_json_values_reject_non_json_and_are_plain_json_when_dumped() -> None:
    complex_value = {
        "null": None,
        "boolean": True,
        "integer": 1,
        "number": 2.5,
        "array": ["text", {"nested": False}],
    }
    value = SuggestedValueContext(
        kind=SuggestedValueKind.EXAMPLE,
        value=complex_value,
        source_pointer="/value",
    )
    assert value.model_dump(mode="json")["value"] == complex_value
    for invalid_value in [
        float("nan"),
        float("inf"),
        b"bytes",
        datetime.now(),
        Decimal("1"),
    ]:
        assert_invalid(
            SuggestedValueContext,
            kind=SuggestedValueKind.EXAMPLE,
            value=invalid_value,
            source_pointer="/value",
        )
    cyclic: list[object] = []
    cyclic.append(cyclic)
    assert_invalid(
        SuggestedValueContext,
        kind=SuggestedValueKind.EXAMPLE,
        value=cyclic,
        source_pointer="/value",
    )


def test_identity_version_metadata_and_operation_key_contracts() -> None:
    assert_invalid(
        RawDocumentIdentity,
        content_sha256="A" * 64,
        size_bytes=1,
    )
    assert_invalid(RawDocumentIdentity, content_sha256="a" * 64, size_bytes=0)
    for version in ["3.1", "2.0.0", "3.2.0", "3.1.x"]:
        assert_invalid(
            OpenAPIVersion,
            family=OpenAPIVersionFamily.OPENAPI_3_1,
            exact_version=version,
        )
    assert_invalid(OpenAPIDocumentMetadata, title=" ", api_version="1")
    for path in ["items", "https://example.test/items", "/items?x=1", "/items#top"]:
        assert_invalid(OperationKey, path=path, method=HttpMethod.GET)


def test_scope_and_operation_sorting_and_snapshot_scope_match_are_required() -> None:
    get = OperationKey(path="/items/{item_id}", method=HttpMethod.GET)
    post = OperationKey(path="/items/{item_id}", method=HttpMethod.POST)
    assert_invalid(OperationScope, selected_operations=(post, get))
    assert_invalid(OperationScope, selected_operations=(get, get))
    ordered_operations = (operation_context(get), operation_context(post))
    mismatched_scope = OperationScope(selected_operations=(get,))
    complete = snapshot().model_copy(
        update={"operation_scope": mismatched_scope, "operations": ordered_operations}
    )
    assert_invalid(
        OpenAPIContextSnapshot,
        **complete.model_dump(),
    )


@pytest.mark.parametrize(
    ("location", "style", "explode"),
    [
        (ParameterLocation.PATH, ParameterStyle.SIMPLE, False),
        (ParameterLocation.QUERY, ParameterStyle.FORM, True),
        (ParameterLocation.HEADER, ParameterStyle.SIMPLE, False),
    ],
)
def test_parameter_serialization_and_path_parameter_contracts(
    location: ParameterLocation, style: ParameterStyle, explode: bool
) -> None:
    parameter = ParameterContext(
        name="item_id",
        location=location,
        required=location is not ParameterLocation.QUERY,
        description=None,
        deprecated=False,
        serialization=ParameterSerializationContext(style=style, explode=explode),
        schema=schema_context(),
        suggested_value=None,
        source_pointer="/parameter",
        declared_scope=ParameterDeclaredScope.OPERATION,
    )
    assert parameter.serialization.style is style
    assert_invalid(
        ParameterContext,
        **{
            **parameter.model_dump(),
            "location": ParameterLocation.PATH,
            "required": False,
        },
    )
    assert_invalid(
        ParameterContext,
        **{
            **parameter.model_dump(),
            "location": ParameterLocation.QUERY,
            "serialization": {"style": "SIMPLE", "explode": False},
        },
    )


def test_operation_rejects_duplicate_headers_reserved_headers_and_bad_path_names() -> (
    None
):
    base = operation_context()
    header = base.parameters[0].model_copy(
        update={
            "name": "X-Request-ID",
            "location": ParameterLocation.HEADER,
            "required": False,
            "serialization": ParameterSerializationContext(
                style=ParameterStyle.SIMPLE, explode=False
            ),
        }
    )
    duplicate_header = header.model_copy(update={"name": "x-request-id"})
    assert_invalid(
        OperationContext,
        **{
            **base.model_dump(),
            "parameters": [base.parameters[0], header, duplicate_header],
        },
    )
    reserved_header = header.model_copy(update={"name": "Authorization"})
    assert_invalid(
        OperationContext,
        **{**base.model_dump(), "parameters": [base.parameters[0], reserved_header]},
    )
    missing_path = base.parameters[0].model_copy(update={"name": "other"})
    assert_invalid(
        OperationContext, **{**base.model_dump(), "parameters": [missing_path]}
    )


def test_response_selectors_are_discriminated_and_stably_ordered() -> None:
    assert DefaultResponse(kind="DEFAULT", value="default").value == "default"
    for value in ["DEFAULT", "Default"]:
        assert_invalid(DefaultResponse, kind="DEFAULT", value=value)
    for status in [99, 600, True]:
        assert_invalid(ExactStatusCode, status_code=status)
    exact = response_context(ExactStatusCode(status_code=200))
    default = response_context(DefaultResponse())
    operation = operation_context(responses=(exact, default))
    assert isinstance(operation.responses[1].selector, DefaultResponse)
    assert_invalid(
        OperationContext, **{**operation.model_dump(), "responses": [default, exact]}
    )
    assert_invalid(
        OperationContext, **{**operation.model_dump(), "responses": [exact, exact]}
    )
    assert OperationContext.model_validate(
        {**operation.model_dump(), "responses": [response_context()]}
    )
    assert OperationContext.model_validate(
        {
            **operation.model_dump(),
            "responses": [
                ResponseContext(
                    selector=ExactStatusCode(status_code=204),
                    description="No content",
                    json_content=(),
                    ignored_content_types=(),
                    source_pointer="/responses/204",
                )
            ],
        }
    )
    with pytest.raises(ValidationError):
        OperationContext.model_validate({**operation.model_dump(), "responses": []})


def test_media_request_body_and_response_content_sorting_contracts() -> None:
    suffix = JsonContentContext(
        media_type=media_type_context(
            "application/vnd.example+json",
            JsonMediaTypeMatchKind.STRUCTURED_JSON_SUFFIX,
        ),
        schema=None,
        suggested_value=None,
        source_pointer="/content/vendor",
    )
    body = RequestBodyContext(
        required=True,
        description=None,
        json_content=(json_content(), suffix),
        ignored_content_types=("text/plain", "text/xml"),
        source_pointer="/requestBody",
    )
    assert body.json_content[0].media_type.normalized_value == "application/json"
    assert_invalid(
        RequestBodyContext,
        **{**body.model_dump(), "ignored_content_types": ["text/xml", "text/plain"]},
    )
    assert_invalid(
        MediaTypeContext,
        declared_value="application/json; charset=utf-8",
        normalized_value="Application/JSON",
        match_kind=JsonMediaTypeMatchKind.EXACT_JSON,
    )


def test_schema_constraints_and_all_schema_kinds() -> None:
    scalar_kinds = [
        SchemaKind.ANY,
        SchemaKind.OBJECT,
        SchemaKind.STRING,
        SchemaKind.INTEGER,
        SchemaKind.NUMBER,
        SchemaKind.BOOLEAN,
        SchemaKind.NULL,
    ]
    for kind in scalar_kinds:
        assert schema_context(kind=kind)
    item_schema = schema_context(kind=SchemaKind.INTEGER)
    array_constraints = ArrayConstraints(items=item_schema, min_items=0, max_items=2)
    assert schema_context(kind=SchemaKind.ARRAY, array_constraints=array_constraints)
    properties = ObjectConstraints(
        properties=(SchemaPropertyContext(name="id", schema=item_schema),),
        required_properties=("id",),
        additional_properties=AdditionalPropertiesPolicy.FORBIDDEN,
    )
    assert schema_context(kind=SchemaKind.ANY, object_constraints=properties)
    assert schema_context(kind=SchemaKind.ANY, array_constraints=array_constraints)
    assert_invalid(SchemaContext, **{**schema_context().model_dump(), "kind": "ARRAY"})
    assert_invalid(
        SchemaContext,
        **{
            **schema_context().model_dump(),
            "read_only": True,
            "write_only": True,
        },
    )
    assert_invalid(
        ObjectConstraints,
        properties=(SchemaPropertyContext(name="z", schema=item_schema),),
        required_properties=("missing",),
        additional_properties=AdditionalPropertiesPolicy.ALLOWED,
    )
    assert_invalid(StringConstraints, min_length=2, max_length=1)
    assert_invalid(ArrayConstraints, items=item_schema, min_items=-1, max_items=None)
    assert_invalid(
        NumericConstraints,
        minimum=NumericBound(value=2, inclusive=True),
        maximum=NumericBound(value=2, inclusive=False),
    )


def test_schema_values_are_frozen_unique_and_json_round_trip() -> None:
    schema = schema_context(
        enum_values=({"a": [1]},),
        default_value={"default": True},
        example_value=["example"],
    )
    restored = SchemaContext.model_validate_json(schema.model_dump_json())
    assert restored == schema
    assert_invalid(
        SchemaContext,
        **{**schema.model_dump(), "enum_values": [{"same": 1}, {"same": 1}]},
    )


def test_security_server_diagnostics_and_references_have_contract_invariants() -> None:
    scheme = SecuritySchemeContext(
        name="apiKey",
        scheme_type=SecuritySchemeType.API_KEY,
        source_pointer="/components/securitySchemes/apiKey",
    )
    requirement = SecurityRequirementContext(scheme=scheme, scopes=())
    alternative = SecurityAlternativeContext(requirements=(requirement,))
    assert EffectiveSecurityContext(
        authentication_required=True, alternatives=(alternative,)
    )
    assert_invalid(
        EffectiveSecurityContext,
        authentication_required=False,
        alternatives=(alternative,),
    )
    assert_invalid(
        EffectiveSecurityContext, authentication_required=True, alternatives=()
    )
    variable = ServerVariableContext(
        name="region",
        default_value="eu",
        allowed_values=("eu", "us"),
        description=None,
    )
    assert ServerCandidateContext(
        url_template="https://{region}.example.test",
        description=None,
        variables=(variable,),
    )
    assert_invalid(
        ServerCandidateContext,
        url_template="https://example.test",
        description=None,
        variables=(),
        authoritative_for_execution=True,
    )
    diagnostic = OpenAPIContextDiagnostic(
        source_pointer="/paths",
        severity=DiagnosticSeverity.WARNING,
        code="IGNORED_MEDIA_TYPE",
        safe_detail="A non-JSON media type was ignored.",
    )
    reference = ReferenceResolutionRecord(
        reference_pointer="/paths/~1items/get/responses/200/$ref",
        original_reference="#/components/responses/Item",
        canonical_target_pointer="/components/responses/Item",
        target_kind=ReferenceTargetKind.RESPONSE,
        chain_depth=1,
        openapi_version_family=OpenAPIVersionFamily.OPENAPI_3_1,
        metadata_override_applied=False,
    )
    complete = snapshot().model_copy(
        update={"diagnostics": (diagnostic,), "reference_resolutions": (reference,)}
    )
    assert OpenAPIContextSnapshot.model_validate(complete.model_dump()) == complete


def test_snapshot_excludes_raw_document_credentials_and_third_party_objects() -> None:
    field_names = set(OpenAPIContextSnapshot.model_fields)
    assert {"raw_document", "root", "credentials", "target_base_url"}.isdisjoint(
        field_names
    )
    assert_invalid(
        SnapshotSourceContext,
        kind=OpenAPISourceKind.REMOTE_HTTP,
        display_value="https://example.test/openapi.json?token=***",
        declared_content_type=None,
        raw_document=b"forbidden",
    )
    assert_invalid(
        SuggestedValueContext,
        kind=SuggestedValueKind.EXAMPLE,
        value=httpx.Response(200),
        source_pointer="/value",
    )
    database_engine = create_engine("sqlite://")
    try:
        assert_invalid(
            SuggestedValueContext,
            kind=SuggestedValueKind.EXAMPLE,
            value=database_engine,
            source_pointer="/value",
        )
    finally:
        database_engine.dispose()
