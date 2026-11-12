"""Where a catalog release is read from: the catalog's site, or a folder on disk (tests, stands)."""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .errors import Refusal

TIMEOUT = 20  # seconds one step may take: the connection, the answer's head, each piece of the file
DEADLINE = 60  # seconds a whole file may take, however steadily its pieces come
_PIECE = 64 * 1024


class DirSource:
    """A release laid out on disk as the site serves it: v1/feed.json, v1/feed.json.sig, the bundles at their paths."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, rel: str, limit: int) -> bytes:
        try:
            with open(self.root / rel, "rb") as f:
                data = f.read(limit + 1)
        except OSError as err:
            raise Refusal(f"{rel}: cannot be read ({type(err).__name__})") from None
        return _within(rel, data, limit)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # a redirect could lead to another host: never followed
        return None


class _Late(Exception):
    """The deadline for a whole file has passed."""


class HttpSource:
    """The catalog over HTTP: GET only, to the one base address and straight to it (a proxy named in the environment
    is not used), with a User-Agent that names this plugin and nothing else of the person's."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self._opener = urllib.request.build_opener(_NoRedirect, urllib.request.ProxyHandler({}))

    def get(self, rel: str, limit: int) -> bytes:
        request = urllib.request.Request(self.base + "/" + rel, method="GET",
                                         headers={"User-Agent": "hr-hermes/" + __version__})
        late = time.monotonic() + DEADLINE
        try:
            with self._opener.open(request, timeout=min(TIMEOUT, DEADLINE)) as response:
                data = _read(response, limit + 1, late)
                if len(data) <= limit and getattr(response, "length", None):  # the answer ended before the length it announced
                    raise http.client.IncompleteRead(data, response.length)
        except _Late:
            raise Refusal(f"{rel}: the catalog did not send the whole file within {DEADLINE:g} seconds") from None
        except urllib.error.HTTPError as err:
            err.close()
            raise Refusal(f"{rel}: the catalog answered {err.code}") from None
        except (OSError, ValueError, http.client.HTTPException) as err:  # the last is not an OSError
            raise Refusal(f"{rel}: the catalog cannot be reached ({type(err).__name__})") from None
        return _within(rel, data, limit)


def _read(response, most: int, late: float) -> bytes:
    """At most `most` bytes of the answer, read piece by piece: the clock is looked at between the pieces, so a file
    that keeps coming a little at a time is given up when its deadline has passed."""
    pieces, size = [], 0
    while size < most:
        if time.monotonic() > late:
            raise _Late
        piece = response.read1(min(_PIECE, most - size))
        if not piece:
            break
        pieces.append(piece)
        size += len(piece)
    return b"".join(pieces)


def _within(rel: str, data: bytes, limit: int) -> bytes:
    if len(data) > limit:
        raise Refusal(f"{rel}: more than {limit} bytes")
    return data
