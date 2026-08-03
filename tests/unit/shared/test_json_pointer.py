import json

import pytest

from apiguard.shared.json_pointer import JsonPointer


@pytest.mark.parametrize(
    ("value", "tokens"),
    [("", ()), ("/a/0", ("a", "0")), ("/~0/~1", ("~", "/")), ("/", ("",))],
)
def test_json_pointer_parses_and_serializes(
    value: str, tokens: tuple[str, ...]
) -> None:
    pointer = JsonPointer(value)
    assert pointer.tokens == tokens
    assert json.dumps(pointer) == json.dumps(value)
    assert {pointer: "value"}[JsonPointer(value)] == "value"


@pytest.mark.parametrize(
    "value", ["#/data", "data", "$.data", "/items/*", "/items[0]", "/a~2", "/a~"]
)
def test_json_pointer_rejects_non_rfc6901_syntax(value: str) -> None:
    with pytest.raises(ValueError):
        JsonPointer(value)
