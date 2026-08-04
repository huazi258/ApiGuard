from __future__ import annotations

import builtins
import socket
from copy import deepcopy
from typing import Any, cast

import pytest

from apiguard.openapi_context.document_parser import JsonValue
from apiguard.openapi_context.models import (
    AdditionalPropertiesPolicy,
    OpenAPIVersionFamily,
    SchemaKind,
)
from apiguard.openapi_context.references import (
    ReferenceResolutionError,
    ReferenceResolutionErrorCode,
)
from apiguard.openapi_context.schema_projector import (
    OpenAPISchemaProjector,
    ProjectedSchema,
    SchemaProjectionError,
    SchemaProjectionErrorCode,
    SchemaProjectionFailureCategory,
)
from apiguard.shared.json_pointer import JsonPointer


def project(
    schema: object,
    family: OpenAPIVersionFamily = OpenAPIVersionFamily.OPENAPI_3_1,
) -> ProjectedSchema:
    root = cast(dict[str, JsonValue], {"schema": schema})
    return OpenAPISchemaProjector(root, family).project(JsonPointer("/schema"))


def assert_error(
    schema: object,
    code: SchemaProjectionErrorCode,
    category: SchemaProjectionFailureCategory,
    family: OpenAPIVersionFamily = OpenAPIVersionFamily.OPENAPI_3_1,
) -> SchemaProjectionError:
    with pytest.raises(SchemaProjectionError) as raised:
        project(schema, family)
    error = raised.value
    assert error.code is code
    assert error.category is category
    assert error.source_pointer == JsonPointer("/schema")
    assert error.openapi_version_family is family
    assert error.retryable is False
    assert str(error) == code.value
    return error


@pytest.mark.parametrize(
    ("type_name", "kind"),
    [
        ("object", SchemaKind.OBJECT),
        ("array", SchemaKind.ARRAY),
        ("string", SchemaKind.STRING),
        ("integer", SchemaKind.INTEGER),
        ("number", SchemaKind.NUMBER),
        ("boolean", SchemaKind.BOOLEAN),
        ("null", SchemaKind.NULL),
    ],
)
def test_projects_supported_31_types(type_name: str, kind: SchemaKind) -> None:
    schema: dict[str, Any] = {"type": type_name}
    if kind is SchemaKind.ARRAY:
        schema["items"] = {"type": "string"}

    result = project(schema)

    assert result.schema.kind is kind
    assert result.schema.nullable is False
    assert result.schema.source_pointer == JsonPointer("/schema")


def test_empty_schema_and_any_conditional_constraints_do_not_infer_type() -> None:
    result = project(
        {
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
            "items": {"type": "integer"},
            "minItems": 1,
        }
    )

    assert result.schema.kind is SchemaKind.ANY
    assert result.schema.object_constraints is not None
    assert result.schema.array_constraints is not None
    assert result.schema.object_constraints.required_properties == ("name",)
    assert result.schema.array_constraints.min_items == 1
    assert project({}).schema.kind is SchemaKind.ANY
    assert_error(
        {"minLength": 1},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )
    assert_error(
        {"minimum": 1},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )


@pytest.mark.parametrize("value", [None, True, 1, "schema", []])
def test_non_object_or_missing_schema_pointer_is_invalid(value: object) -> None:
    assert_error(
        value,
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )
    with pytest.raises(SchemaProjectionError) as raised:
        OpenAPISchemaProjector(
            {"schema": {}}, OpenAPIVersionFamily.OPENAPI_3_1
        ).project(JsonPointer("/missing"))
    assert (
        raised.value.code is SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID
    )


def test_30_nullable_and_31_null_unions_are_normalized() -> None:
    result = project(
        {"type": "string", "nullable": True}, OpenAPIVersionFamily.OPENAPI_3_0
    )
    assert result.schema.kind is SchemaKind.STRING
    assert result.schema.nullable is True
    result = project({"type": ["string", "null"]})
    assert result.schema.kind is SchemaKind.STRING
    assert result.schema.nullable is True
    assert project({"type": ["null"]}).schema.kind is SchemaKind.NULL
    assert_error(
        {"nullable": True},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
        SchemaProjectionFailureCategory.UNSUPPORTED_FEATURE,
    )
    assert_error(
        {"type": ["string", "integer"]},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_UNION_UNSUPPORTED,
        SchemaProjectionFailureCategory.UNSUPPORTED_FEATURE,
    )
    assert_error(
        {"type": ["string"]},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
        SchemaProjectionFailureCategory.UNSUPPORTED_FEATURE,
        OpenAPIVersionFamily.OPENAPI_3_0,
    )


@pytest.mark.parametrize("type_value", ["String", "unknown", 1])
def test_unsupported_types_are_stable(type_value: object) -> None:
    assert_error(
        {"type": type_value},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_TYPE_UNSUPPORTED,
        SchemaProjectionFailureCategory.UNSUPPORTED_FEATURE,
    )


def test_object_projection_sorts_properties_required_and_escapes_pointers() -> None:
    result = project(
        {
            "type": "object",
            "properties": {
                "z": {"type": "string"},
                "a/b~c": {"type": "integer"},
            },
            "required": ["z", "a/b~c"],
            "additionalProperties": True,
        }
    )
    constraints = result.schema.object_constraints
    assert constraints is not None
    assert tuple(item.name for item in constraints.properties) == ("a/b~c", "z")
    assert constraints.required_properties == ("a/b~c", "z")
    assert constraints.additional_properties is AdditionalPropertiesPolicy.ALLOWED
    assert constraints.properties[0].schema.source_pointer == JsonPointer(
        "/schema/properties/a~1b~0c"
    )


@pytest.mark.parametrize(
    ("schema", "code", "category"),
    [
        (
            {"type": "object", "required": ["missing"]},
            SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
            SchemaProjectionFailureCategory.INVALID_DOCUMENT,
        ),
        (
            {"type": "object", "properties": []},
            SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
            SchemaProjectionFailureCategory.INVALID_DOCUMENT,
        ),
        (
            {"type": "object", "additionalProperties": {"type": "string"}},
            SchemaProjectionErrorCode.OPENAPI_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED,
            SchemaProjectionFailureCategory.UNSUPPORTED_FEATURE,
        ),
        (
            {"type": "object", "additionalProperties": "yes"},
            SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
            SchemaProjectionFailureCategory.INVALID_DOCUMENT,
        ),
        (
            {"type": "string", "properties": {}},
            SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
            SchemaProjectionFailureCategory.INVALID_DOCUMENT,
        ),
    ],
)
def test_object_invalid_forms_are_rejected(
    schema: object,
    code: SchemaProjectionErrorCode,
    category: SchemaProjectionFailureCategory,
) -> None:
    assert_error(schema, code, category)


def test_array_items_and_bounds_are_projected() -> None:
    result = project(
        {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2}
    )
    constraints = result.schema.array_constraints
    assert constraints is not None
    assert constraints.items.kind is SchemaKind.STRING
    assert (constraints.min_items, constraints.max_items) == (1, 2)


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "array"},
        {"minItems": 1},
    ],
)
def test_array_missing_items_is_rejected(schema: object) -> None:
    assert_error(
        schema,
        SchemaProjectionErrorCode.OPENAPI_ARRAY_ITEMS_MISSING,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "array", "items": {"type": "string"}, "minItems": True},
        {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 1},
        {"type": "string", "items": {"type": "string"}},
    ],
)
def test_invalid_array_constraints_are_rejected(schema: object) -> None:
    assert_error(
        schema,
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )


def test_string_and_numeric_constraints_cover_both_dialects() -> None:
    string_result = project(
        {
            "type": "string",
            "description": "text",
            "format": "custom",
            "minLength": 1,
            "maxLength": 2,
        }
    )
    assert string_result.schema.string_constraints is not None
    assert string_result.schema.string_constraints.min_length == 1
    result_30 = project(
        {"type": "number", "minimum": 1, "exclusiveMinimum": True},
        OpenAPIVersionFamily.OPENAPI_3_0,
    )
    assert result_30.schema.numeric_constraints is not None
    assert result_30.schema.numeric_constraints.minimum is not None
    assert result_30.schema.numeric_constraints.minimum.inclusive is False
    result_31 = project(
        {
            "type": "number",
            "minimum": 1,
            "exclusiveMinimum": 2,
            "maximum": 5,
            "exclusiveMaximum": 4,
        }
    )
    assert result_31.schema.numeric_constraints is not None
    assert result_31.schema.numeric_constraints.minimum is not None
    assert result_31.schema.numeric_constraints.maximum is not None
    assert result_31.schema.numeric_constraints.minimum.value == 2
    assert result_31.schema.numeric_constraints.minimum.inclusive is False
    assert result_31.schema.numeric_constraints.maximum.value == 4
    assert result_31.schema.numeric_constraints.maximum.inclusive is False


@pytest.mark.parametrize(
    ("schema", "family"),
    [
        (
            {"type": "number", "exclusiveMinimum": True},
            OpenAPIVersionFamily.OPENAPI_3_0,
        ),
        ({"type": "number", "exclusiveMinimum": 1}, OpenAPIVersionFamily.OPENAPI_3_0),
        (
            {"type": "number", "exclusiveMinimum": True},
            OpenAPIVersionFamily.OPENAPI_3_1,
        ),
        ({"type": "number", "minimum": float("nan")}, OpenAPIVersionFamily.OPENAPI_3_1),
        (
            {"type": "number", "minimum": 2, "maximum": 1},
            OpenAPIVersionFamily.OPENAPI_3_1,
        ),
        ({"type": "string", "minimum": 1}, OpenAPIVersionFamily.OPENAPI_3_1),
    ],
)
def test_invalid_numeric_constraints_are_rejected(
    schema: object, family: OpenAPIVersionFamily
) -> None:
    assert_error(
        schema,
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
        family,
    )


def test_enum_default_example_and_read_write_contracts_are_isolated() -> None:
    default = {"nested": ["value"]}
    example = [1, 2]
    result = project(
        {
            "type": ["integer", "null"],
            "enum": [1, None],
            "default": default,
            "example": example,
        }
    )
    default["nested"].append("changed")
    example.append(3)
    assert result.schema.enum_values == (1, None)
    assert result.schema.model_dump()["default_value"] == {"nested": ["value"]}
    assert result.schema.model_dump()["example_value"] == [1, 2]
    assert_error(
        {"type": "integer", "enum": [1, 1.0]},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )
    assert_error(
        {"type": "boolean", "enum": [False, 0]},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )
    assert_error(
        {"type": "object", "enum": ["x"]},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )
    assert_error(
        {"type": "string", "readOnly": True, "writeOnly": True},
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
        SchemaProjectionFailureCategory.INVALID_DOCUMENT,
    )


def test_refs_recursion_and_evidence_are_aggregated_without_root_mutation() -> None:
    root: dict[str, Any] = {
        "schema": {
            "type": "object",
            "properties": {
                "a": {"$ref": "#/components/schemas/Common"},
                "b": {"$ref": "#/components/schemas/Common"},
            },
        },
        "components": {"schemas": {"Common": {"type": "string"}}},
    }
    before = deepcopy(root)
    result = OpenAPISchemaProjector(root, OpenAPIVersionFamily.OPENAPI_3_1).project(
        JsonPointer("/schema")
    )
    assert root == before
    assert [record.reference_pointer for record in result.reference_resolutions] == [
        JsonPointer("/schema/properties/a/$ref"),
        JsonPointer("/schema/properties/b/$ref"),
    ]
    assert result.schema.object_constraints is not None
    assert all(
        property_context.schema.source_pointer
        == JsonPointer("/components/schemas/Common")
        for property_context in result.schema.object_constraints.properties
    )
    root["components"]["schemas"]["Node"] = {
        "type": "object",
        "properties": {"child": {"$ref": "#/components/schemas/Node"}},
    }
    root["schema"] = {"$ref": "#/components/schemas/Node"}
    with pytest.raises(SchemaProjectionError) as raised:
        OpenAPISchemaProjector(root, OpenAPIVersionFamily.OPENAPI_3_1).project(
            JsonPointer("/schema")
        )
    assert (
        raised.value.code
        is SchemaProjectionErrorCode.OPENAPI_SCHEMA_RECURSION_UNSUPPORTED
    )


def test_schema_ref_errors_propagate_and_30_diagnostics_are_preserved() -> None:
    root: dict[str, Any] = {
        "schema": {"$ref": "#/components/schemas/Target", "description": "ignored"},
        "components": {"schemas": {"Target": {"type": "string"}}},
    }
    result = OpenAPISchemaProjector(root, OpenAPIVersionFamily.OPENAPI_3_0).project(
        JsonPointer("/schema")
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "OPENAPI_30_REFERENCE_SIBLING_IGNORED"
    ]
    root["schema"] = {"$ref": "#/components/schemas/Missing"}
    with pytest.raises(ReferenceResolutionError) as raised:
        OpenAPISchemaProjector(root, OpenAPIVersionFamily.OPENAPI_3_1).project(
            JsonPointer("/schema")
        )
    assert (
        raised.value.code
        is ReferenceResolutionErrorCode.OPENAPI_REFERENCE_TARGET_NOT_FOUND
    )


@pytest.mark.parametrize(
    ("schema", "code"),
    [
        (
            {"oneOf": []},
            SchemaProjectionErrorCode.OPENAPI_SCHEMA_COMPOSITION_UNSUPPORTED,
        ),
        (
            {"pattern": ".*"},
            SchemaProjectionErrorCode.OPENAPI_REQUIRED_FEATURE_UNSUPPORTED,
        ),
        (
            {"$schema": "https://example.test"},
            SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
        ),
        (
            {"unknown": True},
            SchemaProjectionErrorCode.OPENAPI_REQUIRED_FEATURE_UNSUPPORTED,
        ),
    ],
)
def test_unsupported_keywords_have_stable_codes(
    schema: object, code: SchemaProjectionErrorCode
) -> None:
    assert_error(schema, code, SchemaProjectionFailureCategory.UNSUPPORTED_FEATURE)
    assert (
        project({"type": "string", "x-note": "ignored", "title": "ignored"}).schema.kind
        is SchemaKind.STRING
    )


def test_projector_performs_zero_external_io_and_failures_preserve_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root: dict[str, Any] = {"schema": {"type": "array"}}
    before = deepcopy(root)

    def fail_io(*_: object, **__: object) -> None:
        raise AssertionError("Projector attempted external I/O")

    monkeypatch.setattr(builtins, "open", fail_io)
    monkeypatch.setattr(socket, "create_connection", fail_io)
    with pytest.raises(SchemaProjectionError) as raised:
        OpenAPISchemaProjector(root, OpenAPIVersionFamily.OPENAPI_3_1).project(
            JsonPointer("/schema")
        )
    assert raised.value.code is SchemaProjectionErrorCode.OPENAPI_ARRAY_ITEMS_MISSING
    assert root == before
