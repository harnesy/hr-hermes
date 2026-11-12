"""Reads JSON the catalog signed, strictly: a field of the wrong type refuses the file, an absent one reads as empty."""

from __future__ import annotations

import json

from .errors import Refusal


def parse(raw: bytes, what: str) -> dict:
    """The JSON object in raw (UTF-8)."""
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=_no_constant)
    except (ValueError, RecursionError) as err:
        raise Refusal(f"{what}: not JSON ({err})") from None
    if not isinstance(doc, dict):
        raise Refusal(f"{what}: want a JSON object")
    return doc


def _no_constant(name: str):
    raise ValueError(f"{name} is not JSON")


def text(doc: dict, key: str, what: str) -> str:
    value = doc.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise Refusal(f"{what}: {key} is not a string")
    # A lone half of a surrogate pair cannot be written as UTF-8: it reads as the replacement character.
    return value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def integer(doc: dict, key: str, what: str) -> int:
    value = doc.get(key)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or abs(value) >= 1 << 63:
        raise Refusal(f"{what}: {key} is not a whole number")
    return value


def flag(doc: dict, key: str, what: str) -> bool:
    value = doc.get(key)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise Refusal(f"{what}: {key} is not true or false")
    return value


def obj(doc: dict, key: str, what: str) -> dict:
    value = doc.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise Refusal(f"{what}: {key} is not an object")
    return value


def items(doc: dict, key: str, what: str) -> list:
    value = doc.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise Refusal(f"{what}: {key} is not a list")
    return value


def objects(doc: dict, key: str, what: str) -> list[dict]:
    """A list of objects; an empty slot (null) reads as an empty object."""
    out = []
    for item in items(doc, key, what):
        if item is not None and not isinstance(item, dict):
            raise Refusal(f"{what}: {key} holds something that is not an object")
        out.append(item or {})
    return out


def texts(doc: dict, key: str, what: str) -> list[str]:
    """A list of strings."""
    return [text({"": item}, "", f"{what}: {key}") for item in items(doc, key, what)]
