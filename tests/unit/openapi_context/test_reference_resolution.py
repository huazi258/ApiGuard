from __future__ import annotations

import builtins
import socket
from collections.abc import Callable
from copy import deepcopy
from typing import Any, cast

import pytest

from apiguard.openapi_context.models import (
    OpenAPIVersionFamily,
    ReferenceTargetKind,
)
from apiguard.openapi_context.references import (
    MAX_REFERENCE_CHAIN_DEPTH,
    OpenAPIReferenceResolver,
    ReferenceResolutionError,
    ReferenceResolutionErrorCode,
    ReferenceResolutionFailureCategory,
)
from apiguard.shared.json_pointer import JsonPointer

_COLLECTIONS = {
    ReferenceTargetKind.SCHEMA: "schemas",
    ReferenceTargetKind.PARAMETER: "parameters",
    ReferenceTargetKind.REQUEST_BODY: "requestBodies",
    ReferenceTargetKind.RESPONSE: "responses",
    ReferenceTargetKind.SECURITY_SCHEME: "securitySchemes",
}


def document() -> dict[str, Any]:
    return {
        "components": {
            "schemas": {"Order": {"type": "object"}},
            "parameters": {"OrderId": {"name": "order_id"}},
            "requestBodies": {"Order": {"description": "order"}},
            "responses": {"Order": {"description": "ok"}},
            "securitySchemes": {"ApiKey": {"type": "apiKey"}},
        },
        "uses": {},
    }


def add_use(
    root: dict[str, Any], name: str, reference: object, **siblings: object
) -> tuple[object, JsonPointer]:
    root["uses"][name] = {"$ref": reference, **siblings}
    return reference, JsonPointer(f"/uses/{name}/$ref")


def resolver(
    root: dict[str, Any],
    family: OpenAPIVersionFamily = OpenAPIVersionFamily.OPENAPI_3_1,
) -> OpenAPIReferenceResolver:
    return OpenAPIReferenceResolver(root, family)


def assert_error(
    root: dict[str, Any],
    reference: object,
    pointer: JsonPointer,
    expected_kind: ReferenceTargetKind,
    code: ReferenceResolutionErrorCode,
    category: ReferenceResolutionFailureCategory,
    *,
    family: OpenAPIVersionFamily = OpenAPIVersionFamily.OPENAPI_3_1,
    expected_reference_pointer: JsonPointer | None = None,
) -> ReferenceResolutionError:
    with pytest.raises(ReferenceResolutionError) as raised:
        resolver(root, family).resolve(reference, pointer, expected_kind)
    error = raised.value
    assert error.code is code
    assert error.category is category
    assert error.reference_pointer == (expected_reference_pointer or pointer)
    assert error.expected_target_kind is expected_kind
    assert error.openapi_version_family is family
    assert error.retryable is False
    assert str(error) == code.value
    return error


@pytest.mark.parametrize("target_kind", list(_COLLECTIONS))
def test_resolves_each_supported_named_component(
    target_kind: ReferenceTargetKind,
) -> None:
    root = document()
    collection = _COLLECTIONS[target_kind]
    name = next(iter(root["components"][collection]))
    reference, pointer = add_use(root, "use", f"#/components/{collection}/{name}")

    result = resolver(root).resolve(reference, pointer, target_kind)

    assert result.target == root["components"][collection][name]
    assert result.canonical_target_pointer == JsonPointer(
        f"/components/{collection}/{name}"
    )
    assert result.target_kind is target_kind
    assert len(result.records) == 1
    assert result.records[0].chain_depth == 1
    assert result.records[0].openapi_version_family is OpenAPIVersionFamily.OPENAPI_3_1
    assert result.diagnostics == ()


def test_component_name_pointer_escapes_and_location_are_strict() -> None:
    root = document()
    root["components"]["schemas"]["A/B"] = {"type": "string"}
    root["components"]["schemas"]["A~B"] = {"type": "number"}
    reference, pointer = add_use(root, "slash", "#/components/schemas/A~1B")
    assert (
        resolver(root)
        .resolve(reference, pointer, ReferenceTargetKind.SCHEMA)
        .target["type"]
        == "string"
    )
    reference, pointer = add_use(root, "tilde", "#/components/schemas/A~0B")
    assert (
        resolver(root)
        .resolve(reference, pointer, ReferenceTargetKind.SCHEMA)
        .target["type"]
        == "number"
    )
    assert_error(
        root,
        reference,
        JsonPointer("/uses/tilde"),
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
    )


@pytest.mark.parametrize(
    ("reference", "code", "category"),
    [
        (None, ReferenceResolutionErrorCode.OPENAPI_REFERENCE_VALUE_INVALID, "invalid"),
        ("", ReferenceResolutionErrorCode.OPENAPI_REFERENCE_VALUE_INVALID, "invalid"),
        (
            "#/components/schemas/A~2B",
            ReferenceResolutionErrorCode.OPENAPI_REFERENCE_POINTER_INVALID,
            "invalid",
        ),
        (
            "#",
            ReferenceResolutionErrorCode.OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED,
            "unsupported",
        ),
        (
            "#Order",
            ReferenceResolutionErrorCode.OPENAPI_REFERENCE_ANCHOR_UNSUPPORTED,
            "unsupported",
        ),
        (
            "#/info",
            ReferenceResolutionErrorCode.OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED,
            "unsupported",
        ),
        (
            "#/paths/~1orders",
            ReferenceResolutionErrorCode.OPENAPI_PATH_ITEM_REFERENCE_UNSUPPORTED,
            "unsupported",
        ),
        (
            "#/components/headers/Trace",
            ReferenceResolutionErrorCode.OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED,
            "unsupported",
        ),
    ],
)
def test_rejects_invalid_fragment_forms(
    reference: object,
    code: ReferenceResolutionErrorCode,
    category: str,
) -> None:
    root = document()
    value, pointer = add_use(root, "invalid", reference)
    assert_error(
        root,
        value,
        pointer,
        ReferenceTargetKind.SCHEMA,
        code,
        (
            ReferenceResolutionFailureCategory.INVALID_DOCUMENT
            if category == "invalid"
            else ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE
        ),
    )


def test_target_failures_and_kind_mismatch_are_stable() -> None:
    root = document()
    reference, pointer = add_use(root, "missing", "#/components/schemas/Missing")
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_TARGET_NOT_FOUND,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
    )
    root["components"]["schemas"]["Broken"] = "not an object"
    reference, pointer = add_use(root, "broken", "#/components/schemas/Broken")
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_TARGET_NOT_OBJECT,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
    )
    reference, pointer = add_use(root, "wrong", "#/components/responses/Order")
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.PARAMETER,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_TARGET_KIND_MISMATCH,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
    )


def test_multihop_records_and_metadata_use_nearest_reference_object() -> None:
    root = document()
    root["components"]["responses"] = {
        "A": {"$ref": "#/components/responses/B", "summary": "B summary"},
        "B": {
            "$ref": "#/components/responses/C",
            "summary": "far summary",
            "description": "far description",
        },
        "C": {"description": "concrete"},
    }
    reference, pointer = add_use(
        root, "response", "#/components/responses/A", summary="near summary"
    )
    result = resolver(root).resolve(reference, pointer, ReferenceTargetKind.RESPONSE)

    assert result.target == {"description": "concrete"}
    assert result.canonical_target_pointer == JsonPointer("/components/responses/C")
    assert [record.chain_depth for record in result.records] == [1, 2, 3]
    assert [str(record.reference_pointer) for record in result.records] == [
        "/uses/response/$ref",
        "/components/responses/A/$ref",
        "/components/responses/B/$ref",
    ]
    assert [record.metadata_override_applied for record in result.records] == [
        True,
        False,
        True,
    ]
    assert result.metadata_override.summary == "near summary"
    assert result.metadata_override.description == "far description"


def test_reference_depth_boundaries_and_cycles() -> None:
    root = document()
    chain = {
        f"S{index}": (
            {"type": "string"}
            if index == MAX_REFERENCE_CHAIN_DEPTH
            else {"$ref": f"#/components/schemas/S{index + 1}"}
        )
        for index in range(1, MAX_REFERENCE_CHAIN_DEPTH + 1)
    }
    root["components"]["schemas"] = chain
    reference, pointer = add_use(root, "depth", "#/components/schemas/S1")
    result = resolver(root).resolve(reference, pointer, ReferenceTargetKind.SCHEMA)
    assert len(result.records) == MAX_REFERENCE_CHAIN_DEPTH
    root["components"]["schemas"]["S33"] = {"type": "string"}
    root["components"]["schemas"]["S32"] = {"$ref": "#/components/schemas/S33"}
    with pytest.raises(ReferenceResolutionError) as raised:
        resolver(root).resolve(reference, pointer, ReferenceTargetKind.SCHEMA)
    assert (
        raised.value.code
        is ReferenceResolutionErrorCode.OPENAPI_REFERENCE_DEPTH_EXCEEDED
    )
    assert raised.value.chain_depth == MAX_REFERENCE_CHAIN_DEPTH + 1
    root = document()
    root["components"]["parameters"] = {
        "A": {"$ref": "#/components/parameters/B"},
        "B": {"$ref": "#/components/parameters/A"},
    }
    reference, pointer = add_use(root, "cycle", "#/components/parameters/A")
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.PARAMETER,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_CYCLE,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
        expected_reference_pointer=JsonPointer("/components/parameters/B/$ref"),
    )
    root["components"]["schemas"] = {"A": {"$ref": "#/components/schemas/A"}}
    reference, pointer = add_use(root, "schema-cycle", "#/components/schemas/A")
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_SCHEMA_RECURSION_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
        expected_reference_pointer=JsonPointer("/components/schemas/A/$ref"),
    )


def test_success_cache_is_per_resolver_and_use_site_metadata_is_independent() -> None:
    root = document()
    root["components"]["responses"] = {
        "A": {"$ref": "#/components/responses/B", "description": "component"},
        "B": {"description": "concrete"},
    }
    first_ref, first_pointer = add_use(
        root, "first", "#/components/responses/A", summary="first"
    )
    second_ref, second_pointer = add_use(
        root, "second", "#/components/responses/A", description="second"
    )
    current = resolver(root)
    first = current.resolve(first_ref, first_pointer, ReferenceTargetKind.RESPONSE)
    second = current.resolve(second_ref, second_pointer, ReferenceTargetKind.RESPONSE)
    assert first.records[0].reference_pointer == first_pointer
    assert second.records[0].reference_pointer == second_pointer
    assert first.metadata_override == type(first.metadata_override)(
        "first", "component"
    )
    assert second.metadata_override == type(second.metadata_override)(None, "second")
    assert resolver(root).resolve(
        first_ref, first_pointer, ReferenceTargetKind.RESPONSE
    )


def test_cached_tail_rechecks_depth_and_reuses_the_legal_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = document()
    root["components"]["schemas"] = {
        f"B{index}": (
            {"type": "string"}
            if index == MAX_REFERENCE_CHAIN_DEPTH
            else {"$ref": f"#/components/schemas/B{index + 1}"}
        )
        for index in range(1, MAX_REFERENCE_CHAIN_DEPTH + 1)
    }
    direct_reference, direct_pointer = add_use(
        root, "direct", "#/components/schemas/B1"
    )
    current = resolver(root)
    assert (
        len(
            current.resolve(
                direct_reference, direct_pointer, ReferenceTargetKind.SCHEMA
            ).records
        )
        == MAX_REFERENCE_CHAIN_DEPTH
    )
    root["components"]["schemas"]["A"] = {"$ref": "#/components/schemas/B1"}
    prefixed_reference, prefixed_pointer = add_use(
        root, "prefixed", "#/components/schemas/A"
    )
    calls: list[JsonPointer] = []
    original_lookup = cast(
        Callable[
            [
                JsonPointer,
                ReferenceTargetKind,
                JsonPointer,
                ReferenceTargetKind,
                int,
            ],
            dict[str, Any],
        ],
        object.__getattribute__(current, "_lookup_target"),
    )

    def count_lookup(
        canonical_target_pointer: JsonPointer,
        target_kind: ReferenceTargetKind,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        chain_depth: int,
    ) -> dict[str, Any]:
        calls.append(canonical_target_pointer)
        return original_lookup(
            canonical_target_pointer,
            target_kind,
            reference_pointer,
            expected_target_kind,
            chain_depth,
        )

    monkeypatch.setattr(current, "_lookup_target", count_lookup)
    with pytest.raises(ReferenceResolutionError) as raised:
        current.resolve(
            prefixed_reference, prefixed_pointer, ReferenceTargetKind.SCHEMA
        )
    assert (
        raised.value.code
        is ReferenceResolutionErrorCode.OPENAPI_REFERENCE_DEPTH_EXCEEDED
    )
    assert raised.value.reference_pointer == JsonPointer("/components/schemas/B31/$ref")
    assert raised.value.canonical_target_pointer == JsonPointer(
        "/components/schemas/B32"
    )
    assert raised.value.chain_depth == 33
    assert calls == [
        JsonPointer("/components/schemas/A"),
        JsonPointer("/components/schemas/B1"),
    ]

    root = document()
    root["components"]["schemas"] = {
        f"B{index}": (
            {"type": "string"}
            if index == MAX_REFERENCE_CHAIN_DEPTH - 1
            else {"$ref": f"#/components/schemas/B{index + 1}"}
        )
        for index in range(1, MAX_REFERENCE_CHAIN_DEPTH)
    }
    direct_reference, direct_pointer = add_use(
        root, "direct", "#/components/schemas/B1"
    )
    current = resolver(root)
    current.resolve(direct_reference, direct_pointer, ReferenceTargetKind.SCHEMA)
    root["components"]["schemas"]["A"] = {"$ref": "#/components/schemas/B1"}
    prefixed_reference, prefixed_pointer = add_use(
        root, "prefixed", "#/components/schemas/A"
    )
    assert (
        len(
            current.resolve(
                prefixed_reference, prefixed_pointer, ReferenceTargetKind.SCHEMA
            ).records
        )
        == MAX_REFERENCE_CHAIN_DEPTH
    )


def test_internal_dynamic_references_and_null_metadata_are_stable() -> None:
    root = document()
    root["components"]["schemas"]["A"] = {"$dynamicRef": "#/components/schemas/Order"}
    reference, pointer = add_use(root, "dynamic", "#/components/schemas/A")
    error = assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
        expected_reference_pointer=JsonPointer("/components/schemas/A/$dynamicRef"),
    )
    assert error.canonical_target_pointer == JsonPointer("/components/schemas/A")
    assert error.chain_depth == 2
    root["components"]["schemas"]["A"] = {
        "$ref": "#/components/schemas/Order",
        "$dynamicRef": "#/components/schemas/Order",
    }
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
        expected_reference_pointer=JsonPointer("/components/schemas/A/$dynamicRef"),
    )
    root = document()
    reference, pointer = add_use(
        root, "null", "#/components/responses/Order", summary=None
    )
    error = assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.RESPONSE,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_METADATA_INVALID,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
    )
    assert error.canonical_target_pointer == JsonPointer("/components/responses/Order")
    assert error.chain_depth == 1
    root["components"]["responses"] = {
        "A": {"$ref": "#/components/responses/B", "description": None},
        "B": {"description": "concrete"},
    }
    reference, pointer = add_use(root, "internal-null", "#/components/responses/A")
    error = assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.RESPONSE,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_METADATA_INVALID,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
        expected_reference_pointer=JsonPointer("/components/responses/A/$ref"),
    )
    assert error.canonical_target_pointer == JsonPointer("/components/responses/B")
    assert error.chain_depth == 2


@pytest.mark.parametrize(
    ("family", "target_kind", "reference"),
    [
        (
            OpenAPIVersionFamily.OPENAPI_3_0,
            ReferenceTargetKind.RESPONSE,
            "#/components/responses/Order",
        ),
        (
            OpenAPIVersionFamily.OPENAPI_3_1,
            ReferenceTargetKind.RESPONSE,
            "#/components/responses/Order",
        ),
        (
            OpenAPIVersionFamily.OPENAPI_3_1,
            ReferenceTargetKind.SCHEMA,
            "#/components/schemas/Order",
        ),
    ],
)
def test_use_site_dynamic_reference_sibling_is_never_ignored(
    family: OpenAPIVersionFamily,
    target_kind: ReferenceTargetKind,
    reference: str,
) -> None:
    root = document()
    value, pointer = add_use(
        root,
        "dynamic-sibling",
        reference,
        **{"$dynamicRef": "not-followed"},
    )
    before = deepcopy(root)

    error = assert_error(
        root,
        value,
        pointer,
        target_kind,
        ReferenceResolutionErrorCode.OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
        family=family,
        expected_reference_pointer=JsonPointer("/uses/dynamic-sibling/$dynamicRef"),
    )

    assert error.canonical_target_pointer == JsonPointer(reference[1:])
    assert error.chain_depth == 1
    assert root == before


def test_internal_schema_siblings_array_indexes_and_component_path_items() -> None:
    root = document()
    root["components"]["schemas"] = {
        "A": {"$ref": "#/components/schemas/B", "description": "unsupported"},
        "B": {"type": "string"},
    }
    reference, pointer = add_use(root, "schema", "#/components/schemas/A")
    error = assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
        expected_reference_pointer=JsonPointer("/components/schemas/A/$ref"),
    )
    assert error.canonical_target_pointer == JsonPointer("/components/schemas/B")
    assert error.chain_depth == 2
    root = document()
    root["uses"] = [{"$ref": "#/components/schemas/Order"}]
    result = resolver(root).resolve(
        root["uses"][0]["$ref"],
        JsonPointer("/uses/0/$ref"),
        ReferenceTargetKind.SCHEMA,
    )
    assert result.target["type"] == "object"
    for invalid_index in ["00", "01", "０", "١", "-1", "+"]:
        assert_error(
            root,
            root["uses"][0]["$ref"],
            JsonPointer(f"/uses/{invalid_index}/$ref"),
            ReferenceTargetKind.SCHEMA,
            ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
            ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
        )
    root = document()
    reference, pointer = add_use(root, "path-item", "#/components/pathItems/SharedPath")
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_PATH_ITEM_REFERENCE_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
    )


def test_openapi_30_siblings_are_diagnosed_without_target_mutation() -> None:
    root = document()
    reference, pointer = add_use(
        root,
        "response",
        "#/components/responses/Order",
        description="ignored",
        **{"x-note": "ignored"},
    )
    before = deepcopy(root)
    result = resolver(root, OpenAPIVersionFamily.OPENAPI_3_0).resolve(
        reference, pointer, ReferenceTargetKind.RESPONSE
    )
    assert root == before
    assert result.metadata_override.summary is None
    assert result.metadata_override.description is None
    assert result.records[0].metadata_override_applied is False
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "OPENAPI_30_REFERENCE_SIBLING_IGNORED",
        "OPENAPI_30_REFERENCE_SIBLING_IGNORED",
    ]
    assert {str(diagnostic.source_pointer) for diagnostic in result.diagnostics} == {
        "/uses/response/description",
        "/uses/response/x-note",
    }


def test_openapi_31_reference_and_schema_sibling_rules() -> None:
    root = document()
    reference, pointer = add_use(
        root,
        "response",
        "#/components/responses/Order",
        summary="summary",
        unexpected="ignored",
    )
    result = resolver(root).resolve(reference, pointer, ReferenceTargetKind.RESPONSE)
    assert result.metadata_override.summary == "summary"
    assert result.diagnostics[0].code == "OPENAPI_31_REFERENCE_SIBLING_IGNORED"
    root["uses"]["response"]["summary"] = 1
    assert_error(
        root,
        reference,
        pointer,
        ReferenceTargetKind.RESPONSE,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_METADATA_INVALID,
        ReferenceResolutionFailureCategory.INVALID_DOCUMENT,
    )
    schema_reference, schema_pointer = add_use(
        root, "schema", "#/components/schemas/Order", **{"x-note": "ignored"}
    )
    schema_result = resolver(root).resolve(
        schema_reference, schema_pointer, ReferenceTargetKind.SCHEMA
    )
    assert (
        schema_result.diagnostics[0].code == "OPENAPI_31_SCHEMA_REF_EXTENSION_IGNORED"
    )
    root["uses"]["schema"]["description"] = "unsupported"
    assert_error(
        root,
        schema_reference,
        schema_pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
    )


@pytest.mark.parametrize(
    "reference",
    [
        "https://example.test/spec.yaml?token=secret#/components/schemas/Order",
        "http://example.test/spec.yaml#/components/schemas/Order",
        "file:///tmp/spec.yaml#/components/schemas/Order",
        "other.yaml#/components/schemas/Order",
        "../common.yaml#/components/schemas/Order",
    ],
)
def test_external_references_are_rejected_without_file_or_network_io(
    monkeypatch: pytest.MonkeyPatch, reference: str
) -> None:
    root = document()
    value, pointer = add_use(root, "external", reference)

    def fail_io(*_: object, **__: object) -> None:
        raise AssertionError("Resolver attempted external I/O")

    monkeypatch.setattr(builtins, "open", fail_io)
    monkeypatch.setattr(socket, "create_connection", fail_io)
    error = assert_error(
        root,
        value,
        pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_REFERENCE_EXTERNAL_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
    )
    assert "secret" not in error.safe_detail


def test_dynamic_reference_and_failed_resolution_leave_the_root_unchanged() -> None:
    root = document()
    value, _ = add_use(root, "dynamic", "#/components/schemas/Order")
    root["uses"]["dynamic"]["$dynamicRef"] = root["uses"]["dynamic"].pop("$ref")
    dynamic_pointer = JsonPointer("/uses/dynamic/$dynamicRef")
    before = deepcopy(root)
    assert_error(
        root,
        value,
        dynamic_pointer,
        ReferenceTargetKind.SCHEMA,
        ReferenceResolutionErrorCode.OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED,
        ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE,
    )
    assert root == before
