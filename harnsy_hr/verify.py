"""The catalog's signatures: Ed25519 over the feed's exact bytes, and the compact JWS inside each bundle."""

from __future__ import annotations

import base64
import binascii
import re

from . import jsonread
from .errors import Refusal

_B64URL = re.compile(r"[A-Za-z0-9_-]*")


def _ed25519_ok(pub: bytes, message: bytes, signature: bytes) -> bool:
    try:  # imported here: the plugin loads without the library, and says so when a signature is to be checked
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        raise Refusal("the Python package `cryptography` is missing: Hermes Agent ships it, so this Python is not "
                      "Hermes' own; a signature cannot be checked without it") from None
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def parse_key(kid: str, b64: str) -> tuple[str, bytes]:
    """A catalog public key as it is handed out: the base64 of the raw 32-byte Ed25519 key."""
    try:
        raw = base64.b64decode(b64.strip(), validate=True)
    except (binascii.Error, ValueError):
        raw = b""
    if len(raw) != 32 or not kid:
        raise Refusal("catalog key: want a kid and the base64 of the raw 32-byte Ed25519 public key")
    return kid, raw


def feed_signature(keys: dict[str, bytes], feed: bytes, sig: bytes) -> str:
    """Checks feed.json.sig ({"kid","sig"}): sig is the Ed25519 signature of the exact bytes of feed.json, in standard
    base64, by the key the signature names. Returns that key's id."""
    doc = jsonread.parse(sig, "feed.json.sig")
    kid, b64 = jsonread.text(doc, "kid", "feed.json.sig"), jsonread.text(doc, "sig", "feed.json.sig")
    if kid not in keys:
        shown = kid if re.fullmatch(r"[A-Za-z0-9_-]{1,16}", kid) else "?"
        raise Refusal(f'feed.json.sig: kid "{shown}" is not a key this plugin knows. The catalog signs with a newer '
                      "key: update the plugin")
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raw = b""
    if not _ed25519_ok(keys[kid], feed, raw):
        raise Refusal("feed.json.sig does not verify")
    return kid


def _b64url(part: str) -> bytes:
    if not _B64URL.fullmatch(part) or len(part) % 4 == 1:
        raise Refusal("catalog.jws: not base64url")
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def jws_claims(kid: str, pub: bytes, token: str) -> dict:
    """Checks signatures/catalog.jws, a compact JWS signed with EdDSA by the catalog key, and returns its claims."""
    parts = token.split(".")
    if len(parts) != 3:
        raise Refusal("catalog.jws: not a compact JWS")
    head, body, sig = (_b64url(p) for p in parts)
    try:
        header = jsonread.parse(head, "catalog.jws")
        named = (jsonread.text(header, "alg", "catalog.jws"), jsonread.text(header, "kid", "catalog.jws"))
    except Refusal:
        named = None
    if named != ("EdDSA", kid):
        raise Refusal("catalog.jws: header names another algorithm or key")
    if not _ed25519_ok(pub, (parts[0] + "." + parts[1]).encode(), sig):
        raise Refusal("catalog.jws does not verify")
    return jsonread.parse(body, "catalog.jws claims")
