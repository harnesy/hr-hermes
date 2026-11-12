"""Where a catalog release is read from: the catalog's site, or a folder on disk (tests, stands)."""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .errors import Refusal

TIMEOUT = 20  # seconds; nothing waits longer for the catalog


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


class HttpSource:
    """The catalog over HTTP: GET only, to the one base address, with a User-Agent that names this plugin and nothing
    else of the person's."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self._opener = urllib.request.build_opener(_NoRedirect)

    def get(self, rel: str, limit: int) -> bytes:
        request = urllib.request.Request(self.base + "/" + rel, method="GET",
                                         headers={"User-Agent": "hr-hermes/" + __version__})
        try:
            with self._opener.open(request, timeout=TIMEOUT) as response:
                data = response.read(limit + 1)
                if len(data) <= limit and getattr(response, "length", None):  # the answer ended before the length it announced
                    raise http.client.IncompleteRead(data, response.length)
        except urllib.error.HTTPError as err:
            err.close()
            raise Refusal(f"{rel}: the catalog answered {err.code}") from None
        except (OSError, ValueError, http.client.HTTPException) as err:  # the last is not an OSError
            raise Refusal(f"{rel}: the catalog cannot be reached ({type(err).__name__})") from None
        return _within(rel, data, limit)


def _within(rel: str, data: bytes, limit: int) -> bytes:
    if len(data) > limit:
        raise Refusal(f"{rel}: more than {limit} bytes")
    return data
