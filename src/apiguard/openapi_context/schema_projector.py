"""Deterministically project ApiGuard's supported OpenAPI Schema subset."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn, cast

from pydantic import ValidationError

from apiguard.openapi_context.document_parser import JsonValue
from apiguard.openapi_context.models import (
    AdditionalPropertiesPolicy,
    ArrayConstraints,
    NumericBound,
    NumericConstraints,
    ObjectConstraints,
    OpenAPIContextDiagnostic,
    OpenAPIVersionFamily,
    ReferenceResolutionRecord,
    ReferenceTargetKind,
    SchemaContext,
    SchemaKind,
    SchemaPropertyContext,
    StringConstraints,
)
from apiguard.openapi_context.references import OpenAPIReferenceResolver
from apiguard.shared.json_pointer import JsonPointer

_ARRAY_INDEX_PATTERN = re.compile(r"0|[1-9][0-9]*", re.ASCII)
_COMPOSITION_KEYWORDS = frozenset(
    {
        "oneOf",
        "allOf",
        "anyOf",
        "not",
        "if",
        "then",
        "else",
        "dependentSchemas",
        "unevaluatedProperties",
        "discriminator",
    }
)
_REQUIRED_FEATURE_KEYWORDS = frozenset(
    {
        "pattern",
        "multipleOf",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "contains",
        "prefixItems",
        "patternProperties",
        "propertyNames",
        "dependentRequired",
        "unevaluatedItems",
        "const",
    }
)
_DIALECT_KEYWORDS = frozenset({"$schema", "$id", "$anchor", "$dynamicAnchor", "$defs"})
_KNOWN_KEYWORDS = frozenset(
    {
        "$ref",
        "$dynamicRef",
        "type",
        "nullable",
        "description",
        "format",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "enum",
        "default",
        "example",
        "readOnly",
        "writeOnly",
        "title",
        "deprecated",
        "xml",
        "externalDocs",
        "examples",
        *_COMPOSITION_KEYWORDS,
        *_REQUIRED_FEATURE_KEYWORDS,
        *_DIALECT_KEYWORDS,
    }
)
_TYPE_KINDS = {
    "object": SchemaKind.OBJECT,
    "array": SchemaKind.ARRAY,
    "string": SchemaKind.STRING,
    "integer": SchemaKind.INTEGER,
    "number": SchemaKind.NUMBER,
    "boolean": SchemaKind.BOOLEAN,
    "null": SchemaKind.NULL,
}


class SchemaProjectionFailureCategory(StrEnum):
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"


class SchemaProjectionErrorCode(StrEnum):
    OPENAPI_SCHEMA_STRUCTURE_INVALID = "OPENAPI_SCHEMA_STRUCTURE_INVALID"
    OPENAPI_SCHEMA_TYPE_UNSUPPORTED = "OPENAPI_SCHEMA_TYPE_UNSUPPORTED"
    OPENAPI_SCHEMA_UNION_UNSUPPORTED = "OPENAPI_SCHEMA_UNION_UNSUPPORTED"
    OPENAPI_SCHEMA_COMPOSITION_UNSUPPORTED = "OPENAPI_SCHEMA_COMPOSITION_UNSUPPORTED"
    OPENAPI_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED = (
        "OPENAPI_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED"
    )
    OPENAPI_ARRAY_ITEMS_MISSING = "OPENAPI_ARRAY_ITEMS_MISSING"
    OPENAPI_SCHEMA_CONSTRAINT_INVALID = "OPENAPI_SCHEMA_CONSTRAINT_INVALID"
    OPENAPI_SCHEMA_DIALECT_UNSUPPORTED = "OPENAPI_SCHEMA_DIALECT_UNSUPPORTED"
    OPENAPI_REQUIRED_FEATURE_UNSUPPORTED = "OPENAPI_REQUIRED_FEATURE_UNSUPPORTED"
    OPENAPI_SCHEMA_RECURSION_UNSUPPORTED = "OPENAPI_SCHEMA_RECURSION_UNSUPPORTED"


_UNSUPPORTED_CODES = frozenset(
    {
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_TYPE_UNSUPPORTED,
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_UNION_UNSUPPORTED,
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_COMPOSITION_UNSUPPORTED,
        SchemaProjectionErrorCode.OPENAPI_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED,
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
        SchemaProjectionErrorCode.OPENAPI_REQUIRED_FEATURE_UNSUPPORTED,
        SchemaProjectionErrorCode.OPENAPI_SCHEMA_RECURSION_UNSUPPORTED,
    }
)


class SchemaProjectionError(Exception):
    """A stable, non-retryable schema projection failure."""

    def __init__(
        self,
        code: SchemaProjectionErrorCode,
        source_pointer: JsonPointer,
        openapi_version_family: OpenAPIVersionFamily,
    ) -> None:
        self.code = code
        self.category = (
            SchemaProjectionFailureCategory.UNSUPPORTED_FEATURE
            if code in _UNSUPPORTED_CODES
            else SchemaProjectionFailureCategory.INVALID_DOCUMENT
        )
        self.source_pointer = source_pointer
        self.openapi_version_family = openapi_version_family
        self.retryable = False
        self.safe_detail = "OpenAPI schema could not be projected."
        super().__init__(code.value)


@dataclass(frozen=True)
class ProjectedSchema:
    """An immutable supported Schema projection and its resolution evidence."""

    schema: SchemaContext
    reference_resolutions: tuple[ReferenceResolutionRecord, ...]
    diagnostics: tuple[OpenAPIContextDiagnostic, ...]


@dataclass(frozen=True)
class _Projection:
    schema: SchemaContext
    reference_resolutions: tuple[ReferenceResolutionRecord, ...]
    diagnostics: tuple[OpenAPIContextDiagnostic, ...]


class OpenAPISchemaProjector:
    """Project Schema Objects from one parsed OpenAPI document without I/O."""

    def __init__(
        self,
        document_root: dict[str, JsonValue],
        openapi_version_family: OpenAPIVersionFamily,
    ) -> None:
        self._document_root = document_root
        self._openapi_version_family = openapi_version_family
        self._resolver = OpenAPIReferenceResolver(document_root, openapi_version_family)

    def project(self, source_pointer: JsonPointer) -> ProjectedSchema:
        schema = self._schema_at(source_pointer)
        projection = self._project_schema(schema, source_pointer, set())
        return ProjectedSchema(
            schema=projection.schema,
            reference_resolutions=projection.reference_resolutions,
            diagnostics=projection.diagnostics,
        )

    def _project_schema(
        self,
        schema: dict[str, JsonValue],
        source_pointer: JsonPointer,
        active_pointers: set[JsonPointer],
    ) -> _Projection:
        if source_pointer in active_pointers:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_RECURSION_UNSUPPORTED,
                source_pointer,
            )
        active_pointers.add(source_pointer)
        try:
            return self._project_active_schema(schema, source_pointer, active_pointers)
        finally:
            active_pointers.remove(source_pointer)

    def _project_active_schema(
        self,
        schema: dict[str, JsonValue],
        source_pointer: JsonPointer,
        active_pointers: set[JsonPointer],
    ) -> _Projection:
        if "$ref" in schema:
            resolved = self._resolver.resolve(
                schema["$ref"],
                _child_pointer(source_pointer, "$ref"),
                ReferenceTargetKind.SCHEMA,
            )
            nested = self._project_schema(
                cast(dict[str, JsonValue], resolved.target),
                resolved.canonical_target_pointer,
                active_pointers,
            )
            return _Projection(
                schema=nested.schema,
                reference_resolutions=(
                    *resolved.records,
                    *nested.reference_resolutions,
                ),
                diagnostics=(*resolved.diagnostics, *nested.diagnostics),
            )
        self._reject_unsupported_keywords(schema, source_pointer)
        if "$dynamicRef" in schema:
            self._resolver.resolve(
                schema["$dynamicRef"],
                _child_pointer(source_pointer, "$dynamicRef"),
                ReferenceTargetKind.SCHEMA,
            )

        kind, nullable = self._project_type(schema, source_pointer)
        description = self._optional_string(schema, "description", source_pointer)
        format_value = self._optional_string(schema, "format", source_pointer)
        read_only = self._optional_bool(schema, "readOnly", source_pointer)
        write_only = self._optional_bool(schema, "writeOnly", source_pointer)
        if read_only and write_only:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        string_constraints = self._project_string_constraints(
            schema, kind, source_pointer
        )
        numeric_constraints = self._project_numeric_constraints(
            schema, kind, source_pointer
        )
        object_constraints, property_records, property_diagnostics = (
            self._project_object_constraints(
                schema, kind, source_pointer, active_pointers
            )
        )
        array_constraints, item_records, item_diagnostics = (
            self._project_array_constraints(
                schema, kind, source_pointer, active_pointers
            )
        )
        enum_values = self._project_enum(schema, kind, nullable, source_pointer)
        default_value = self._optional_json_value(schema, "default", source_pointer)
        example_value = self._optional_json_value(schema, "example", source_pointer)
        try:
            context = SchemaContext(
                kind=kind,
                nullable=nullable,
                description=description,
                format=format_value,
                enum_values=enum_values,
                default_value=default_value,
                example_value=example_value,
                read_only=read_only,
                write_only=write_only,
                string_constraints=string_constraints,
                numeric_constraints=numeric_constraints,
                array_constraints=array_constraints,
                object_constraints=object_constraints,
                source_pointer=source_pointer,
            )
        except (ValidationError, ValueError) as error:
            raise SchemaProjectionError(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
                self._openapi_version_family,
            ) from error
        return _Projection(
            schema=context,
            reference_resolutions=(*property_records, *item_records),
            diagnostics=(*property_diagnostics, *item_diagnostics),
        )

    def _project_type(
        self, schema: dict[str, JsonValue], source_pointer: JsonPointer
    ) -> tuple[SchemaKind, bool]:
        has_type = "type" in schema
        type_value = schema.get("type")
        if self._openapi_version_family is OpenAPIVersionFamily.OPENAPI_3_1:
            if "nullable" in schema:
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
                    source_pointer,
                )
            if not has_type:
                return SchemaKind.ANY, False
            if type(type_value) is list:
                return self._project_31_union(
                    cast(list[JsonValue], type_value), source_pointer
                )
            if type(type_value) is not str:
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_TYPE_UNSUPPORTED,
                    source_pointer,
                )
            return self._single_kind(type_value, source_pointer), False

        nullable = self._optional_bool(schema, "nullable", source_pointer)
        if not has_type:
            if nullable:
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                    source_pointer,
                )
            return SchemaKind.ANY, False
        if type(type_value) is list or type_value == "null":
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
                source_pointer,
            )
        if type(type_value) is not str:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_TYPE_UNSUPPORTED,
                source_pointer,
            )
        kind = self._single_kind(type_value, source_pointer)
        if kind is SchemaKind.NULL:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
                source_pointer,
            )
        return kind, nullable

    def _single_kind(self, type_name: str, source_pointer: JsonPointer) -> SchemaKind:
        kind = _TYPE_KINDS.get(type_name)
        if kind is None:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_TYPE_UNSUPPORTED,
                source_pointer,
            )
        return kind

    def _project_31_union(
        self, type_values: list[JsonValue], source_pointer: JsonPointer
    ) -> tuple[SchemaKind, bool]:
        if not type_values or any(type(value) is not str for value in type_values):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_UNION_UNSUPPORTED,
                source_pointer,
            )
        names = cast(list[str], type_values)
        if len(set(names)) != len(names) or len(names) > 2:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_UNION_UNSUPPORTED,
                source_pointer,
            )
        if len(names) == 1:
            return self._single_kind(names[0], source_pointer), False
        if "null" not in names:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_UNION_UNSUPPORTED,
                source_pointer,
            )
        non_null_name = next(name for name in names if name != "null")
        kind = self._single_kind(non_null_name, source_pointer)
        if kind is SchemaKind.NULL:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_UNION_UNSUPPORTED,
                source_pointer,
            )
        return kind, True

    def _project_string_constraints(
        self,
        schema: dict[str, JsonValue],
        kind: SchemaKind,
        source_pointer: JsonPointer,
    ) -> StringConstraints | None:
        keys = ("minLength", "maxLength")
        if not any(key in schema for key in keys):
            return None
        if kind is not SchemaKind.STRING:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        minimum = self._optional_nonnegative_int(schema, "minLength", source_pointer)
        maximum = self._optional_nonnegative_int(schema, "maxLength", source_pointer)
        if minimum is not None and maximum is not None and minimum > maximum:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        return StringConstraints(min_length=minimum, max_length=maximum)

    def _project_numeric_constraints(
        self,
        schema: dict[str, JsonValue],
        kind: SchemaKind,
        source_pointer: JsonPointer,
    ) -> NumericConstraints | None:
        keys = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
        if not any(key in schema for key in keys):
            return None
        if kind not in {SchemaKind.INTEGER, SchemaKind.NUMBER}:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        if self._openapi_version_family is OpenAPIVersionFamily.OPENAPI_3_0:
            minimum = self._optional_number(schema, "minimum", source_pointer)
            maximum = self._optional_number(schema, "maximum", source_pointer)
            min_exclusive = self._optional_exclusive_30(
                schema, "exclusiveMinimum", minimum, source_pointer
            )
            max_exclusive = self._optional_exclusive_30(
                schema, "exclusiveMaximum", maximum, source_pointer
            )
            lower = (
                NumericBound(value=minimum, inclusive=not min_exclusive)
                if minimum is not None
                else None
            )
            upper = (
                NumericBound(value=maximum, inclusive=not max_exclusive)
                if maximum is not None
                else None
            )
        else:
            lower = _stricter_lower(
                self._optional_bound(schema, "minimum", True, source_pointer),
                self._optional_bound(schema, "exclusiveMinimum", False, source_pointer),
            )
            upper = _stricter_upper(
                self._optional_bound(schema, "maximum", True, source_pointer),
                self._optional_bound(schema, "exclusiveMaximum", False, source_pointer),
            )
        self._validate_interval(lower, upper, source_pointer)
        return NumericConstraints(minimum=lower, maximum=upper)

    def _project_object_constraints(
        self,
        schema: dict[str, JsonValue],
        kind: SchemaKind,
        source_pointer: JsonPointer,
        active_pointers: set[JsonPointer],
    ) -> tuple[
        ObjectConstraints | None,
        tuple[ReferenceResolutionRecord, ...],
        tuple[OpenAPIContextDiagnostic, ...],
    ]:
        fields = ("properties", "required", "additionalProperties")
        if kind is not SchemaKind.OBJECT and kind is not SchemaKind.ANY:
            if any(field in schema for field in fields):
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                    source_pointer,
                )
            return None, (), ()
        create = kind is SchemaKind.OBJECT or any(field in schema for field in fields)
        if not create:
            return None, (), ()
        properties_value = schema.get("properties", {})
        if type(properties_value) is not dict:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
                source_pointer,
            )
        properties = cast(dict[str, JsonValue], properties_value)
        projected_properties: list[SchemaPropertyContext] = []
        records: list[ReferenceResolutionRecord] = []
        diagnostics: list[OpenAPIContextDiagnostic] = []
        for name in sorted(properties):
            child_pointer = _child_pointer(
                _child_pointer(source_pointer, "properties"), name
            )
            child = properties[name]
            if type(child) is not dict:
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
                    child_pointer,
                )
            nested = self._project_schema(
                cast(dict[str, JsonValue], child), child_pointer, active_pointers
            )
            try:
                projected_properties.append(
                    SchemaPropertyContext(name=name, schema=nested.schema)
                )
            except ValidationError as error:
                raise SchemaProjectionError(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                    child_pointer,
                    self._openapi_version_family,
                ) from error
            records.extend(nested.reference_resolutions)
            diagnostics.extend(nested.diagnostics)
        required = self._project_required(schema, set(properties), source_pointer)
        policy = self._project_additional_properties(schema, source_pointer)
        try:
            object_constraints = ObjectConstraints(
                properties=tuple(projected_properties),
                required_properties=required,
                additional_properties=policy,
            )
        except (ValidationError, ValueError) as error:
            raise SchemaProjectionError(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
                self._openapi_version_family,
            ) from error
        return object_constraints, tuple(records), tuple(diagnostics)

    def _project_array_constraints(
        self,
        schema: dict[str, JsonValue],
        kind: SchemaKind,
        source_pointer: JsonPointer,
        active_pointers: set[JsonPointer],
    ) -> tuple[
        ArrayConstraints | None,
        tuple[ReferenceResolutionRecord, ...],
        tuple[OpenAPIContextDiagnostic, ...],
    ]:
        fields = ("items", "minItems", "maxItems")
        has_fields = any(field in schema for field in fields)
        if kind is not SchemaKind.ARRAY and kind is not SchemaKind.ANY:
            if has_fields:
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                    source_pointer,
                )
            return None, (), ()
        if kind is SchemaKind.ARRAY and "items" not in schema:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_ARRAY_ITEMS_MISSING, source_pointer
            )
        if kind is SchemaKind.ANY and not has_fields:
            return None, (), ()
        if "items" not in schema:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_ARRAY_ITEMS_MISSING, source_pointer
            )
        items_pointer = _child_pointer(source_pointer, "items")
        items = schema["items"]
        if type(items) is not dict:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
                items_pointer,
            )
        nested = self._project_schema(
            cast(dict[str, JsonValue], items), items_pointer, active_pointers
        )
        minimum = self._optional_nonnegative_int(schema, "minItems", source_pointer)
        maximum = self._optional_nonnegative_int(schema, "maxItems", source_pointer)
        if minimum is not None and maximum is not None and minimum > maximum:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        try:
            constraints = ArrayConstraints(
                items=nested.schema, min_items=minimum, max_items=maximum
            )
        except (ValidationError, ValueError) as error:
            raise SchemaProjectionError(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
                self._openapi_version_family,
            ) from error
        return constraints, nested.reference_resolutions, nested.diagnostics

    def _project_enum(
        self,
        schema: dict[str, JsonValue],
        kind: SchemaKind,
        nullable: bool,
        source_pointer: JsonPointer,
    ) -> tuple[JsonValue, ...]:
        if "enum" not in schema:
            return ()
        enum = schema["enum"]
        if type(enum) is not list or not enum:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        if kind in {SchemaKind.OBJECT, SchemaKind.ARRAY}:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        values = cast(list[JsonValue], enum)
        seen: set[tuple[object, ...]] = set()
        for value in values:
            key = _scalar_key(value)
            if key is None or key in seen or not _enum_matches(kind, nullable, value):
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                    source_pointer,
                )
            seen.add(key)
        return tuple(values)

    def _project_required(
        self,
        schema: dict[str, JsonValue],
        property_names: set[str],
        source_pointer: JsonPointer,
    ) -> tuple[str, ...]:
        if "required" not in schema:
            return ()
        required = schema["required"]
        if type(required) is not list or any(
            type(name) is not str for name in required
        ):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        names = cast(list[str], required)
        if len(set(names)) != len(names) or not set(names).issubset(property_names):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        return tuple(sorted(names))

    def _project_additional_properties(
        self, schema: dict[str, JsonValue], source_pointer: JsonPointer
    ) -> AdditionalPropertiesPolicy:
        if "additionalProperties" not in schema:
            return AdditionalPropertiesPolicy.UNSPECIFIED
        value = schema["additionalProperties"]
        if type(value) is bool:
            return (
                AdditionalPropertiesPolicy.ALLOWED
                if value
                else AdditionalPropertiesPolicy.FORBIDDEN
            )
        if type(value) is dict:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED,
                source_pointer,
            )
        self._raise(
            SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID, source_pointer
        )

    def _reject_unsupported_keywords(
        self, schema: dict[str, JsonValue], source_pointer: JsonPointer
    ) -> None:
        if any(keyword in schema for keyword in _DIALECT_KEYWORDS):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_DIALECT_UNSUPPORTED,
                source_pointer,
            )
        if any(keyword in schema for keyword in _COMPOSITION_KEYWORDS):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_COMPOSITION_UNSUPPORTED,
                source_pointer,
            )
        if (
            "additionalProperties" in schema
            and type(schema["additionalProperties"]) is dict
        ):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED,
                source_pointer,
            )
        if any(keyword in schema for keyword in _REQUIRED_FEATURE_KEYWORDS):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_REQUIRED_FEATURE_UNSUPPORTED,
                source_pointer,
            )
        for keyword in schema:
            if keyword not in _KNOWN_KEYWORDS and not keyword.startswith("x-"):
                self._raise(
                    SchemaProjectionErrorCode.OPENAPI_REQUIRED_FEATURE_UNSUPPORTED,
                    source_pointer,
                )

    def _schema_at(self, source_pointer: JsonPointer) -> dict[str, JsonValue]:
        try:
            value = _evaluate_pointer(self._document_root, source_pointer)
        except _PointerLookupError:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
                source_pointer,
            )
        if type(value) is not dict:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
                source_pointer,
            )
        return cast(dict[str, JsonValue], value)

    def _optional_string(
        self, schema: dict[str, JsonValue], name: str, source_pointer: JsonPointer
    ) -> str | None:
        if name not in schema:
            return None
        value = schema[name]
        if type(value) is not str:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        return value

    def _optional_bool(
        self, schema: dict[str, JsonValue], name: str, source_pointer: JsonPointer
    ) -> bool:
        if name not in schema:
            return False
        value = schema[name]
        if type(value) is not bool:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        return value

    def _optional_nonnegative_int(
        self, schema: dict[str, JsonValue], name: str, source_pointer: JsonPointer
    ) -> int | None:
        if name not in schema:
            return None
        value = schema[name]
        if type(value) is not int or value < 0:
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        return value

    def _optional_number(
        self, schema: dict[str, JsonValue], name: str, source_pointer: JsonPointer
    ) -> int | float | None:
        if name not in schema:
            return None
        value = schema[name]
        if not _is_finite_number(value):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        return cast(int | float, value)

    def _optional_exclusive_30(
        self,
        schema: dict[str, JsonValue],
        name: str,
        bound: int | float | None,
        source_pointer: JsonPointer,
    ) -> bool:
        if name not in schema:
            return False
        value = schema[name]
        if type(value) is not bool or (value and bound is None):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )
        return value

    def _optional_bound(
        self,
        schema: dict[str, JsonValue],
        name: str,
        inclusive: bool,
        source_pointer: JsonPointer,
    ) -> NumericBound | None:
        value = self._optional_number(schema, name, source_pointer)
        if value is None:
            return None
        return NumericBound(value=value, inclusive=inclusive)

    def _optional_json_value(
        self, schema: dict[str, JsonValue], name: str, source_pointer: JsonPointer
    ) -> JsonValue | None:
        if name not in schema:
            return None
        value = schema[name]
        if not _is_json_value(value, set()):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_STRUCTURE_INVALID,
                source_pointer,
            )
        return value

    def _validate_interval(
        self,
        minimum: NumericBound | None,
        maximum: NumericBound | None,
        source_pointer: JsonPointer,
    ) -> None:
        if minimum is None or maximum is None:
            return
        if minimum.value > maximum.value or (
            minimum.value == maximum.value
            and not (minimum.inclusive and maximum.inclusive)
        ):
            self._raise(
                SchemaProjectionErrorCode.OPENAPI_SCHEMA_CONSTRAINT_INVALID,
                source_pointer,
            )

    def _raise(
        self, code: SchemaProjectionErrorCode, source_pointer: JsonPointer
    ) -> NoReturn:
        raise SchemaProjectionError(code, source_pointer, self._openapi_version_family)


class _PointerLookupError(Exception):
    pass


def _evaluate_pointer(root: object, pointer: JsonPointer) -> object:
    current = root
    for token in pointer.tokens:
        if type(current) is dict:
            mapping = cast(dict[str, object], current)
            if token not in mapping:
                raise _PointerLookupError
            current = mapping[token]
        elif type(current) is list:
            if _ARRAY_INDEX_PATTERN.fullmatch(token) is None:
                raise _PointerLookupError
            index = int(token)
            sequence = cast(list[object], current)
            if index >= len(sequence):
                raise _PointerLookupError
            current = sequence[index]
        else:
            raise _PointerLookupError
    return current


def _child_pointer(parent: JsonPointer, token: str) -> JsonPointer:
    prefix = "" if parent == "" else str(parent)
    return JsonPointer(f"{prefix}/{token.replace('~', '~0').replace('/', '~1')}")


def _stricter_lower(
    first: NumericBound | None, second: NumericBound | None
) -> NumericBound | None:
    if first is None:
        return second
    if second is None:
        return first
    if second.value > first.value or (
        second.value == first.value and not second.inclusive and first.inclusive
    ):
        return second
    return first


def _stricter_upper(
    first: NumericBound | None, second: NumericBound | None
) -> NumericBound | None:
    if first is None:
        return second
    if second is None:
        return first
    if second.value < first.value or (
        second.value == first.value and not second.inclusive and first.inclusive
    ):
        return second
    return first


def _is_finite_number(value: object) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _scalar_key(value: JsonValue) -> tuple[object, ...] | None:
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int or type(value) is float:
        if _is_finite_number(value):
            return ("number", value)
        return None
    if type(value) is str:
        return ("string", value)
    return None


def _enum_matches(kind: SchemaKind, nullable: bool, value: JsonValue) -> bool:
    if value is None:
        return kind is SchemaKind.NULL or nullable
    if kind is SchemaKind.ANY:
        return _scalar_key(value) is not None
    if kind is SchemaKind.STRING:
        return type(value) is str
    if kind is SchemaKind.INTEGER:
        return type(value) is int
    if kind is SchemaKind.NUMBER:
        return _is_finite_number(value)
    if kind is SchemaKind.BOOLEAN:
        return type(value) is bool
    return False


def _is_json_value(value: object, active_ids: set[int]) -> bool:
    if value is None or type(value) in {bool, int, str}:
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        sequence = cast(list[object], value)
        value_id = id(sequence)
        if value_id in active_ids:
            return False
        active_ids.add(value_id)
        try:
            return all(_is_json_value(item, active_ids) for item in sequence)
        finally:
            active_ids.remove(value_id)
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        value_id = id(mapping)
        if value_id in active_ids:
            return False
        active_ids.add(value_id)
        try:
            return all(
                type(key) is str and _is_json_value(item, active_ids)
                for key, item in mapping.items()
            )
        finally:
            active_ids.remove(value_id)
    return False
