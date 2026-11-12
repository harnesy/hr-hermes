"""The catalog's public keys, and the two settings a test stand may change."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import Refusal
from .verify import parse_key

# ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
# │ THE CATALOG'S PUBLIC KEYS, by key id: the base64 of the raw 32-byte Ed25519 public key.                        │
# │                                                                                                                │
# │ EMPTY SLOT: the catalog's key `c1` is not published yet. Until its line is added here, every command that     │
# │ needs the catalog refuses and says so. A key is public by nature; adding one is a change of the plugin's code │
# │ and reaches people only as a new release of the plugin.                                                       │
# │                                                                                                                │
# │     "c1": "<base64 of the raw 32-byte key>",                                                                   │
# └──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
CATALOG_KEYS: dict[str, str] = {
}

DEFAULT_BASE = "https://hr.harnsy.dev"

# For test stands only. FEED replaces the address the catalog is fetched from (the feed must still name
# hr.harnsy.dev in every bundle url: only the path of each is fetched from the stand). PUB is `<kid>:<base64 key>`
# and replaces the keys above.
FEED_ENV, PUB_ENV = "HARNSY_HR_FEED", "HARNSY_HR_PUB"

TEST_LINE = ("A test catalog is in use (HARNSY_HR_FEED or HARNSY_HR_PUB is set): what you see is not checked against "
             "hr.harnsy.dev's own key.")
NO_KEY = ("This version of the plugin holds no catalog key yet, so it cannot check the catalog's signature, and it "
          "installs nothing it cannot check. Update the plugin when a release with the key is out.")


@dataclass
class Setup:
    """Where the catalog is fetched from and the keys its signatures are checked with."""

    base: str
    keys: dict[str, bytes]
    test: bool  # a test catalog is in use: every command says so first

    def need_keys(self) -> dict[str, bytes]:
        if not self.keys:
            raise Refusal(NO_KEY)
        return self.keys


def setup(environ) -> Setup:
    base, pub = environ.get(FEED_ENV, "").strip(), environ.get(PUB_ENV, "").strip()
    keys = dict(parse_key(kid, b64) for kid, b64 in CATALOG_KEYS.items())
    if pub:
        kid, _, b64 = pub.partition(":")
        try:
            keys = dict([parse_key(kid, b64)])
        except Refusal:
            raise Refusal(f"{PUB_ENV}: want <kid>:<base64 of the raw 32-byte Ed25519 public key>") from None
    if base:
        url = urlsplit(base)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.query or url.fragment:
            raise Refusal(f"{FEED_ENV}: want an http(s) address without a query, for example http://127.0.0.1:8850")
    return Setup(base=base or DEFAULT_BASE, keys=keys, test=bool(base or pub))
