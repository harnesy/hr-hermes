"""The catalog's public keys, and the two settings a test stand may change.

Which catalog is read and which key it is checked with is decided here and nowhere else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import Refusal
from .verify import parse_key

# ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
# │ THE CATALOG'S PUBLIC KEYS, by key id: the base64 of the raw 32-byte Ed25519 public key.                      │
# │                                                                                                              │
# │ `c1` is the key hr.harnsy.dev signs its feed and every employee's file with. A feed signed under a key id    │
# │ that is not listed here is refused with «update the plugin». A key is public by nature; adding or dropping   │
# │ one is a change of the plugin's code and reaches people only as a new release of the plugin.                 │
# └──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
CATALOG_KEYS: dict[str, str] = {
    "c1": "WMZK4GiSTfBo5ZeMNZjDRextsTDGfoCU1KF6jlrqVjM=",
}

DEFAULT_BASE = "https://hr.harnsy.dev"

# For test stands only. FEED replaces the address the catalog is fetched from (the feed must still name
# hr.harnsy.dev in every bundle url: only the path of each is fetched from the stand). PUB is `<kid>:<base64 key>`
# and replaces the keys above. Hermes fills the environment from `<Hermes home>/.env`, so a variable alone is not the
# person's word: a test catalog is read only when the command line says --test-catalog as well, and never from a chat.
FEED_ENV, PUB_ENV = "HARNSY_HR_FEED", "HARNSY_HR_PUB"
FLAG = "--test-catalog"
_LOOPBACK = ("127.0.0.1", "::1", "localhost")
_KID = re.compile(r"[A-Za-z0-9_-]{1,16}")
_ADDRESS = re.compile(r"[\x21-\x7e]+")  # it is printed in the question: nothing a terminal would obey or hide

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
    note: str = ""  # names a test catalog, for the question the plugin asks; empty for hr.harnsy.dev

    def need_keys(self) -> dict[str, bytes]:
        if not self.keys:
            raise Refusal(NO_KEY)
        return self.keys

    def seq_slot(self, kid: str) -> str:
        """The name the feed number of that key is kept under: a test catalog's is kept apart, so that a stand can
        neither read nor raise the number kept for the catalog's own key."""
        return "test:" + kid if self.test else kid


def _built_in() -> dict[str, bytes]:
    return dict(parse_key(kid, b64) for kid, b64 in CATALOG_KEYS.items())


def setup(environ, test_catalog: bool = False, chat: bool = False) -> Setup:
    """Decides the catalog and the keys, before anything is fetched or written. `test_catalog` is the word
    --test-catalog of the command line; a chat command has no such word."""
    base, pub = environ.get(FEED_ENV, "").strip(), environ.get(PUB_ENV, "").strip()
    named = [name for name, value in ((FEED_ENV, base), (PUB_ENV, pub)) if value]
    if not named:
        if test_catalog:
            raise Refusal(f"{FLAG} was given, but neither {FEED_ENV} nor {PUB_ENV} is set: there is no test catalog to read.")
        return Setup(base=DEFAULT_BASE, keys=_built_in(), test=False)
    if chat:
        raise Refusal(f"A test catalog is set in this machine's environment ({' and '.join(named)}). It is never read "
                      "from a chat; nothing was fetched.")
    if not test_catalog:
        both = len(named) > 1
        raise Refusal(f"{' and '.join(named)} {'are' if both else 'is'} set, but {FLAG} was not given: a test catalog is "
                      "read only when the command line says so. Nothing was fetched or written. Unset the "
                      f"variable{'s' if both else ''} to read hr.harnsy.dev.")
    keys = _stand_keys(pub) if pub else _built_in()
    if base:
        _check_address(base)
    kids = ", ".join(keys) or "none"
    note = (f"This is a TEST catalog, not hr.harnsy.dev: address {base or DEFAULT_BASE}, key {kids} "
            f"({'from ' + PUB_ENV if pub else 'the built-in one'}).")
    return Setup(base=base or DEFAULT_BASE, keys=keys, test=True, note=note)


def _stand_keys(pub: str) -> dict[str, bytes]:
    kid, _, b64 = pub.partition(":")
    try:
        if not _KID.fullmatch(kid):
            raise Refusal("kid")
        return dict([parse_key(kid, b64)])
    except Refusal:
        raise Refusal(f"{PUB_ENV}: want <kid>:<base64 of the raw 32-byte Ed25519 public key>, the kid of at most 16 "
                      "letters, digits, - or _") from None


def _check_address(base: str) -> None:
    try:
        url = urlsplit(base)
        ok = bool(_ADDRESS.fullmatch(base) and url.scheme in ("http", "https") and url.hostname) \
            and not (url.username or url.password or url.query or url.fragment or url.port == 0)
    except ValueError:  # brackets that hold no address, a port that is not a number
        ok = False
    if not ok:
        raise Refusal(f"{FEED_ENV}: want an http(s) address without a query, for example http://127.0.0.1:8850")
    if url.scheme == "http" and url.hostname not in _LOOPBACK:
        raise Refusal(f"{FEED_ENV}: plain http is taken only for this machine itself (127.0.0.1, [::1], localhost); use "
                      "https for any other address.")
