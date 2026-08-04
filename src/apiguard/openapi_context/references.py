"""Pure in-memory resolution of supported local OpenAPI component references."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import NoReturn, cast

from apiguard.openapi_context.document_parser import JsonValue
from apiguard.openapi_context.models import (
    DiagnosticSeverity,
    OpenAPIContextDiagnostic,
    OpenAPIVersionFamily,
    ReferenceResolutionRecord,
    ReferenceTargetKind,
)
from apiguard.shared.json_pointer import JsonPointer

MAX_REFERENCE_CHAIN_DEPTH = 32


class ReferenceResolutionFailureCategory(StrEnum):
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"


class ReferenceResolutionErrorCode(StrEnum):
    OPENAPI_REFERENCE_VALUE_INVALID = "OPENAPI_REFERENCE_VALUE_INVALID"
    OPENAPI_REFERENCE_LOCATION_INVALID = "OPENAPI_REFERENCE_LOCATION_INVALID"
    OPENAPI_REFERENCE_POINTER_INVALID = "OPENAPI_REFERENCE_POINTER_INVALID"
    OPENAPI_REFERENCE_EXTERNAL_UNSUPPORTED = "OPENAPI_REFERENCE_EXTERNAL_UNSUPPORTED"
    OPENAPI_REFERENCE_ANCHOR_UNSUPPORTED = "OPENAPI_REFERENCE_ANCHOR_UNSUPPORTED"
    OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED = "OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED"
    OPENAPI_PATH_ITEM_REFERENCE_UNSUPPORTED = "OPENAPI_PATH_ITEM_REFERENCE_UNSUPPORTED"
    OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED = (
        "OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED"
    )
    OPENAPI_REFERENCE_TARGET_NOT_FOUND = "OPENAPI_REFERENCE_TARGET_NOT_FOUND"
    OPENAPI_REFERENCE_TARGET_NOT_OBJECT = "OPENAPI_REFERENCE_TARGET_NOT_OBJECT"
    OPENAPI_REFERENCE_TARGET_KIND_MISMATCH = "OPENAPI_REFERENCE_TARGET_KIND_MISMATCH"
    OPENAPI_REFERENCE_CYCLE = "OPENAPI_REFERENCE_CYCLE"
    OPENAPI_REFERENCE_DEPTH_EXCEEDED = "OPENAPI_REFERENCE_DEPTH_EXCEEDED"
    OPENAPI_REFERENCE_METADATA_INVALID = "OPENAPI_REFERENCE_METADATA_INVALID"
    OPENAPI_SCHEMA_RECURSION_UNSUPPORTED = "OPENAPI_SCHEMA_RECURSION_UNSUPPORTED"
    OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED = "OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED"


_UNSUPPORTED_CODES = {
    ReferenceResolutionErrorCode.OPENAPI_REFERENCE_EXTERNAL_UNSUPPORTED,
    ReferenceResolutionErrorCode.OPENAPI_REFERENCE_ANCHOR_UNSUPPORTED,
    ReferenceResolutionErrorCode.OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED,
    ReferenceResolutionErrorCode.OPENAPI_PATH_ITEM_REFERENCE_UNSUPPORTED,
    ReferenceResolutionErrorCode.OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED,
    ReferenceResolutionErrorCode.OPENAPI_REFERENCE_DEPTH_EXCEEDED,
    ReferenceResolutionErrorCode.OPENAPI_SCHEMA_RECURSION_UNSUPPORTED,
    ReferenceResolutionErrorCode.OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED,
}

_COLLECTION_TARGET_KINDS = {
    "schemas": ReferenceTargetKind.SCHEMA,
    "parameters": ReferenceTargetKind.PARAMETER,
    "requestBodies": ReferenceTargetKind.REQUEST_BODY,
    "responses": ReferenceTargetKind.RESPONSE,
    "securitySchemes": ReferenceTargetKind.SECURITY_SCHEME,
}


class ReferenceResolutionError(Exception):
    """A stable, non-retryable local-reference resolution failure."""

    def __init__(
        self,
        code: ReferenceResolutionErrorCode,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        openapi_version_family: OpenAPIVersionFamily,
        *,
        canonical_target_pointer: JsonPointer | None,
        chain_depth: int,
    ) -> None:
        self.code = code
        self.category = (
            ReferenceResolutionFailureCategory.UNSUPPORTED_FEATURE
            if code in _UNSUPPORTED_CODES
            else ReferenceResolutionFailureCategory.INVALID_DOCUMENT
        )
        self.reference_pointer = reference_pointer
        self.expected_target_kind = expected_target_kind
        self.openapi_version_family = openapi_version_family
        self.canonical_target_pointer = canonical_target_pointer
        self.chain_depth = chain_depth
        self.retryable = False
        self.safe_detail = "OpenAPI reference could not be resolved."
        super().__init__(code.value)


@dataclass(frozen=True)
class ReferenceMetadataOverride:
    """Effective OpenAPI 3.1 Reference Object metadata, without target mutation."""

    summary: str | None
    description: str | None


@dataclass(frozen=True)
class ResolvedReference:
    """Final local component target and immutable resolution trace."""

    target: Mapping[str, JsonValue]
    canonical_target_pointer: JsonPointer
    target_kind: ReferenceTargetKind
    metadata_override: ReferenceMetadataOverride
    records: tuple[ReferenceResolutionRecord, ...]
    diagnostics: tuple[OpenAPIContextDiagnostic, ...]


@dataclass(frozen=True)
class _ReferenceHop:
    reference_pointer: JsonPointer
    original_reference: str
    canonical_target_pointer: JsonPointer
    metadata: ReferenceMetadataOverride
    diagnostics: tuple[OpenAPIContextDiagnostic, ...]


@dataclass(frozen=True)
class _CachedTail:
    target: dict[str, JsonValue]
    canonical_target_pointer: JsonPointer
    hops: tuple[_ReferenceHop, ...]


class OpenAPIReferenceResolver:
    """Resolve supported fragment-only component references without external I/O."""

    def __init__(
        self,
        document_root: dict[str, JsonValue],
        openapi_version_family: OpenAPIVersionFamily,
    ) -> None:
        self._document_root = document_root
        self._openapi_version_family = openapi_version_family
        self._successful_tails: dict[
            tuple[JsonPointer, ReferenceTargetKind], _CachedTail
        ] = {}

    def resolve(
        self,
        reference: object,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
    ) -> ResolvedReference:
        self._validate_reference_location(
            reference, reference_pointer, expected_target_kind
        )
        if reference_pointer.tokens[-1] == "$dynamicRef":
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_DYNAMIC_REFERENCE_UNSUPPORTED,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=0,
            )
        original_reference = self._validate_reference_value(
            reference, reference_pointer, expected_target_kind, 1
        )
        direct_pointer, target_kind = self._parse_component_reference(
            original_reference, reference_pointer, expected_target_kind, 1
        )
        target = self._lookup_target(
            direct_pointer,
            target_kind,
            reference_pointer,
            expected_target_kind,
            1,
        )
        metadata, diagnostics = self._inspect_siblings(
            self._parent_mapping(reference_pointer, expected_target_kind),
            reference_pointer,
            expected_target_kind,
            1,
        )
        direct_hop = _ReferenceHop(
            reference_pointer=reference_pointer,
            original_reference=original_reference,
            canonical_target_pointer=direct_pointer,
            metadata=metadata,
            diagnostics=diagnostics,
        )
        tail = self._resolve_tail(
            target,
            direct_pointer,
            target_kind,
            reference_pointer,
            expected_target_kind,
            1,
            {direct_pointer},
        )
        hops = (direct_hop, *tail.hops)
        effective_metadata, records = self._records_with_effective_metadata(
            hops, expected_target_kind
        )
        all_diagnostics = tuple(
            diagnostic for hop in hops for diagnostic in hop.diagnostics
        )
        return ResolvedReference(
            target=MappingProxyType(tail.target),
            canonical_target_pointer=tail.canonical_target_pointer,
            target_kind=target_kind,
            metadata_override=effective_metadata,
            records=records,
            diagnostics=tuple(sorted(all_diagnostics, key=_diagnostic_sort_key)),
        )

    def _resolve_tail(
        self,
        target: dict[str, JsonValue],
        target_pointer: JsonPointer,
        target_kind: ReferenceTargetKind,
        initial_reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        depth: int,
        active_pointers: set[JsonPointer],
    ) -> _CachedTail:
        cache_key = (target_pointer, target_kind)
        cached = self._successful_tails.get(cache_key)
        if cached is not None:
            return cached
        if "$ref" not in target:
            resolved = _CachedTail(target, target_pointer, ())
            self._successful_tails[cache_key] = resolved
            return resolved
        reference_value = target["$ref"]
        internal_reference_pointer = _child_pointer(target_pointer, "$ref")
        original_reference = self._validate_reference_value(
            reference_value,
            internal_reference_pointer,
            expected_target_kind,
            depth + 1,
        )
        direct_pointer, direct_kind = self._parse_component_reference(
            original_reference,
            internal_reference_pointer,
            expected_target_kind,
            depth + 1,
        )
        if depth >= MAX_REFERENCE_CHAIN_DEPTH:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_DEPTH_EXCEEDED,
                internal_reference_pointer,
                expected_target_kind,
                canonical_target_pointer=direct_pointer,
                chain_depth=depth + 1,
            )
        if direct_pointer in active_pointers:
            cycle_code = (
                ReferenceResolutionErrorCode.OPENAPI_SCHEMA_RECURSION_UNSUPPORTED
                if expected_target_kind is ReferenceTargetKind.SCHEMA
                else ReferenceResolutionErrorCode.OPENAPI_REFERENCE_CYCLE
            )
            self._raise(
                cycle_code,
                internal_reference_pointer,
                expected_target_kind,
                canonical_target_pointer=direct_pointer,
                chain_depth=depth + 1,
            )
        metadata, diagnostics = self._inspect_siblings(
            target,
            internal_reference_pointer,
            expected_target_kind,
            depth,
        )
        direct_target = self._lookup_target(
            direct_pointer,
            direct_kind,
            internal_reference_pointer,
            expected_target_kind,
            depth + 1,
        )
        active_pointers.add(direct_pointer)
        try:
            nested = self._resolve_tail(
                direct_target,
                direct_pointer,
                direct_kind,
                initial_reference_pointer,
                expected_target_kind,
                depth + 1,
                active_pointers,
            )
        finally:
            active_pointers.remove(direct_pointer)
        result = _CachedTail(
            target=nested.target,
            canonical_target_pointer=nested.canonical_target_pointer,
            hops=(
                _ReferenceHop(
                    reference_pointer=internal_reference_pointer,
                    original_reference=original_reference,
                    canonical_target_pointer=direct_pointer,
                    metadata=metadata,
                    diagnostics=diagnostics,
                ),
                *nested.hops,
            ),
        )
        self._successful_tails[cache_key] = result
        return result

    def _validate_reference_location(
        self,
        reference: object,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
    ) -> None:
        if not reference_pointer.tokens:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=0,
            )
        token = reference_pointer.tokens[-1]
        if token not in {"$ref", "$dynamicRef"}:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=0,
            )
        try:
            actual_reference = _evaluate_pointer(self._document_root, reference_pointer)
        except _PointerLookupError:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=0,
            )
        if actual_reference != reference:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=0,
            )

    def _validate_reference_value(
        self,
        reference: object,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        chain_depth: int,
    ) -> str:
        if type(reference) is not str or not reference:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_VALUE_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        return reference

    def _parse_component_reference(
        self,
        reference: str,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        chain_depth: int,
    ) -> tuple[JsonPointer, ReferenceTargetKind]:
        if not reference.startswith("#"):
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_EXTERNAL_UNSUPPORTED,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        if reference == "#":
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        if not reference.startswith("#/"):
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_ANCHOR_UNSUPPORTED,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        try:
            fragment = JsonPointer(reference[1:])
        except ValueError:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_POINTER_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        tokens = fragment.tokens
        if tokens and tokens[0] == "paths":
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_PATH_ITEM_REFERENCE_UNSUPPORTED,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        if len(tokens) != 3 or tokens[0] != "components":
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        collection, component_name = tokens[1:]
        target_kind = _COLLECTION_TARGET_KINDS.get(collection)
        if target_kind is None or not component_name:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_COMPONENT_POINTER_UNSUPPORTED,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        assert target_kind is not None
        canonical_pointer = _component_pointer(collection, component_name)
        if target_kind is not expected_target_kind:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_TARGET_KIND_MISMATCH,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=canonical_pointer,
                chain_depth=chain_depth,
            )
        return canonical_pointer, target_kind

    def _lookup_target(
        self,
        canonical_target_pointer: JsonPointer,
        target_kind: ReferenceTargetKind,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        chain_depth: int,
    ) -> dict[str, JsonValue]:
        try:
            target = _evaluate_pointer(self._document_root, canonical_target_pointer)
        except _PointerLookupError:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_TARGET_NOT_FOUND,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=canonical_target_pointer,
                chain_depth=chain_depth,
            )
        if type(target) is not dict:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_TARGET_NOT_OBJECT,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=canonical_target_pointer,
                chain_depth=chain_depth,
            )
        return cast(dict[str, JsonValue], target)

    def _parent_mapping(
        self,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
    ) -> dict[str, JsonValue]:
        parent_pointer = _parent_pointer(reference_pointer)
        try:
            parent = _evaluate_pointer(self._document_root, parent_pointer)
        except _PointerLookupError:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=0,
            )
        if type(parent) is not dict:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_LOCATION_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=0,
            )
        return cast(dict[str, JsonValue], parent)

    def _inspect_siblings(
        self,
        reference_object: dict[str, JsonValue],
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        chain_depth: int,
    ) -> tuple[ReferenceMetadataOverride, tuple[OpenAPIContextDiagnostic, ...]]:
        siblings = tuple(key for key in reference_object if key != "$ref")
        if self._openapi_version_family is OpenAPIVersionFamily.OPENAPI_3_0:
            return (
                ReferenceMetadataOverride(None, None),
                tuple(
                    _sibling_diagnostic(
                        _child_pointer(_parent_pointer(reference_pointer), sibling),
                        "OPENAPI_30_REFERENCE_SIBLING_IGNORED",
                    )
                    for sibling in siblings
                ),
            )
        if expected_target_kind is ReferenceTargetKind.SCHEMA:
            unsupported_siblings = tuple(
                sibling for sibling in siblings if not sibling.startswith("x-")
            )
            if unsupported_siblings:
                self._raise(
                    ReferenceResolutionErrorCode.OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED,
                    reference_pointer,
                    expected_target_kind,
                    canonical_target_pointer=None,
                    chain_depth=chain_depth,
                )
            return (
                ReferenceMetadataOverride(None, None),
                tuple(
                    _sibling_diagnostic(
                        _child_pointer(_parent_pointer(reference_pointer), sibling),
                        "OPENAPI_31_SCHEMA_REF_EXTENSION_IGNORED",
                    )
                    for sibling in siblings
                ),
            )
        summary = reference_object.get("summary")
        description = reference_object.get("description")
        if summary is not None and type(summary) is not str:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_METADATA_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        if description is not None and type(description) is not str:
            self._raise(
                ReferenceResolutionErrorCode.OPENAPI_REFERENCE_METADATA_INVALID,
                reference_pointer,
                expected_target_kind,
                canonical_target_pointer=None,
                chain_depth=chain_depth,
            )
        ignored_siblings = tuple(
            sibling for sibling in siblings if sibling not in {"summary", "description"}
        )
        return (
            ReferenceMetadataOverride(summary, description),
            tuple(
                _sibling_diagnostic(
                    _child_pointer(_parent_pointer(reference_pointer), sibling),
                    "OPENAPI_31_REFERENCE_SIBLING_IGNORED",
                )
                for sibling in ignored_siblings
            ),
        )

    def _records_with_effective_metadata(
        self,
        hops: tuple[_ReferenceHop, ...],
        target_kind: ReferenceTargetKind,
    ) -> tuple[ReferenceMetadataOverride, tuple[ReferenceResolutionRecord, ...]]:
        effective_summary: str | None = None
        effective_description: str | None = None
        records: list[ReferenceResolutionRecord] = []
        for depth, hop in enumerate(hops, start=1):
            summary_applied = (
                hop.metadata.summary is not None and effective_summary is None
            )
            description_applied = (
                hop.metadata.description is not None and effective_description is None
            )
            if summary_applied:
                effective_summary = hop.metadata.summary
            if description_applied:
                effective_description = hop.metadata.description
            records.append(
                ReferenceResolutionRecord(
                    reference_pointer=hop.reference_pointer,
                    original_reference=hop.original_reference,
                    canonical_target_pointer=hop.canonical_target_pointer,
                    target_kind=target_kind,
                    chain_depth=depth,
                    openapi_version_family=self._openapi_version_family,
                    metadata_override_applied=summary_applied or description_applied,
                )
            )
        return ReferenceMetadataOverride(
            effective_summary, effective_description
        ), tuple(records)

    def _raise(
        self,
        code: ReferenceResolutionErrorCode,
        reference_pointer: JsonPointer,
        expected_target_kind: ReferenceTargetKind,
        *,
        canonical_target_pointer: JsonPointer | None,
        chain_depth: int,
    ) -> NoReturn:
        raise ReferenceResolutionError(
            code,
            reference_pointer,
            expected_target_kind,
            self._openapi_version_family,
            canonical_target_pointer=canonical_target_pointer,
            chain_depth=chain_depth,
        )


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
            if not token.isdecimal():
                raise _PointerLookupError
            index = int(token)
            sequence = cast(list[object], current)
            if index >= len(sequence):
                raise _PointerLookupError
            current = sequence[index]
        else:
            raise _PointerLookupError
    return current


def _component_pointer(collection: str, component_name: str) -> JsonPointer:
    return JsonPointer(
        f"/components/{_escape_pointer_token(collection)}/"
        f"{_escape_pointer_token(component_name)}"
    )


def _child_pointer(parent: JsonPointer, token: str) -> JsonPointer:
    prefix = "" if parent == "" else str(parent)
    return JsonPointer(f"{prefix}/{_escape_pointer_token(token)}")


def _parent_pointer(pointer: JsonPointer) -> JsonPointer:
    tokens = pointer.tokens[:-1]
    return JsonPointer("".join(f"/{_escape_pointer_token(token)}" for token in tokens))


def _escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _sibling_diagnostic(
    source_pointer: JsonPointer, code: str
) -> OpenAPIContextDiagnostic:
    return OpenAPIContextDiagnostic(
        source_pointer=source_pointer,
        severity=DiagnosticSeverity.WARNING,
        code=code,
        safe_detail="OpenAPI Reference Object sibling was ignored.",
    )


def _diagnostic_sort_key(
    diagnostic: OpenAPIContextDiagnostic,
) -> tuple[str, str, str]:
    return (
        str(diagnostic.source_pointer),
        diagnostic.severity.value,
        diagnostic.code,
    )
