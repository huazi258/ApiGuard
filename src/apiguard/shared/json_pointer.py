"""Strict RFC 6901 JSON Pointer syntax value object."""


class JsonPointer(str):
    """An immutable, JSON-serializable RFC 6901 pointer without evaluation."""

    def __new__(cls, value: str) -> "JsonPointer":
        if value and not value.startswith("/"):
            raise ValueError("A JSON Pointer must be empty or start with '/'.")
        tokens = [] if value == "" else value[1:].split("/")
        for token in tokens:
            if any(character in token for character in "*[]"):
                raise ValueError(
                    "JSON Pointer tokens cannot use wildcard or bracket syntax."
                )
            index = 0
            while index < len(token):
                if token[index] == "~":
                    if index + 1 == len(token) or token[index + 1] not in "01":
                        raise ValueError("JSON Pointer escapes must be '~0' or '~1'.")
                    index += 2
                else:
                    index += 1
        return str.__new__(cls, value)

    @property
    def tokens(self) -> tuple[str, ...]:
        if self == "":
            return ()
        return tuple(
            token.replace("~1", "/").replace("~0", "~") for token in self[1:].split("/")
        )
