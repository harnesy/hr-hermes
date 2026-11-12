"""A signed release of the hr.harnsy.dev catalog, checked on the person's machine.

Anything that does not verify is refused: the feed's signature, its version and expiry, where each bundle is, each
bundle's size, hashes and catalog signature. The rules are the catalog's own (bundle v1).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from . import grammar, jsonread, verify
from .bundle import MAX_BUNDLE, clean_relative, open_bundle
from .errors import Refusal
from .types import Employee, Entry, Feed

HOST = "hr.harnsy.dev"
MAX_FEED = 4 << 20  # feed.json
FEED, FEED_SIG = "v1/feed.json", "v1/feed.json.sig"

_RFC3339 = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)")


def _moment(text: str) -> datetime | None:
    """An RFC 3339 moment, or None."""
    if not _RFC3339.fullmatch(text):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def bundle_path(url: str, host: str) -> str | None:
    """The path of a feed url on the catalog's site; None when the url is not a clean path on the catalog's own https
    host."""
    prefix = "https://" + host + "/"
    rel = url[len(prefix):] if url.startswith(prefix) else ""
    if not clean_relative(rel) or "?" in rel or "#" in rel:
        return None
    return rel


def _served(doc: dict, host: str, revoked: set[str]) -> Entry | None:
    """One entry of the feed, checked; None for what bundle v1 does not serve: another kind, a revoked version."""
    e = Entry.read(doc)
    if e.kind != "employee":
        return None
    if not grammar.is_id(e.id) or not grammar.is_version(e.version):
        raise Refusal("feed.json lists an employee whose id or version is not in the catalog's form "
                      "(<publisher>/<name>, MAJOR.MINOR.PATCH)")
    for name, link in (("cv_url", e.cv_url), ("avatar_url", e.avatar_url)):
        if link and not link.startswith("https://" + host + "/"):
            raise Refusal(f"{e.id}: {name} not on {host}")  # shown to a person and named in the notice as the source
    if e.id + "@" + e.version in revoked:
        return None
    if bundle_path(e.url, host) is None:
        raise Refusal(f"{e.id}: url not on {host}")
    return e


def read_feed(keys: dict[str, bytes], feed: bytes, sig: bytes, host: str, now: datetime) -> Feed:
    """Verifies feed.json under the key its signature names and returns the employees it serves. The signature is
    checked over the exact bytes before anything in them is read."""
    kid = verify.feed_signature(keys, feed, sig)
    doc = jsonread.parse(feed, "feed.json")
    v, seq = jsonread.integer(doc, "v", "feed.json"), jsonread.integer(doc, "seq", "feed.json")
    expires = jsonread.text(doc, "expires", "feed.json")
    at = _moment(expires)
    if v != 1 or at is None or at <= now:
        shown = expires if at else "?"
        raise Refusal(f"feed.json: v {v}, expires {shown} (now {now.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ})")
    revoked = set(jsonread.texts(doc, "revoked", "feed.json"))
    served = (_served(raw, host, revoked) for raw in jsonread.objects(doc, "bundles", "feed.json"))
    return Feed(kid=kid, seq=seq, expires=at, entries=[e for e in served if e is not None])


def fetch_feed(source, keys: dict[str, bytes], host: str, now: datetime) -> Feed:
    feed = source.get(FEED, MAX_FEED)
    return read_feed(keys, feed, source.get(FEED_SIG, MAX_FEED), host, now)


def fetch_employee(source, keys: dict[str, bytes], host: str, feed: Feed, e: Entry) -> Employee:
    """Downloads one bundle of a verified feed and verifies it."""
    try:
        file = source.get(bundle_path(e.url, host), MAX_BUNDLE)
        return open_bundle(feed.kid, keys[feed.kid], host, e, file)
    except Refusal as err:
        raise Refusal(f"{e.id}@{e.version}: {err}") from None


def load_release(source, keys: dict[str, bytes], host: str, now: datetime) -> tuple[Feed, list[Employee]]:
    """The whole release: the feed and every employee it serves. Any fault refuses all of it."""
    feed = fetch_feed(source, keys, host, now)
    return feed, [fetch_employee(source, keys, host, feed, e) for e in feed.entries]
