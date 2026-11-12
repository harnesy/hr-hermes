"""The catalog over HTTP: GET only, one address, a User-Agent that names the plugin, no redirect followed, bounded."""

from __future__ import annotations

import http.server
import tempfile
import threading
import unittest
from pathlib import Path

from harnsy_hr import __version__, catalog
from harnsy_hr.errors import Refusal
from harnsy_hr.sources import HttpSource
from tests.kit import HOST, Kit, sample


class Recorder(http.server.SimpleHTTPRequestHandler):
    seen: list[tuple[str, str, dict]] = []

    def do_GET(self) -> None:
        self.seen.append((self.command, self.path, dict(self.headers)))
        if self.path.startswith("/moved/"):
            self.send_response(302)
            self.send_header("Location", "/" + self.path.removeprefix("/moved/"))
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args) -> None:
        pass


class HttpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.k = Kit()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.k.release(self.dir, [self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer"))])
        Recorder.seen = []
        handler = lambda *a, **kw: Recorder(*a, directory=str(self.dir), **kw)  # noqa: E731
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def test_a_release_loads_over_http_and_only_says_who_asks(self) -> None:
        feed, employees = catalog.load_release(HttpSource(self.base + "/"), self.k.keys, HOST, self.k.now)
        self.assertEqual([e.entry.id for e in employees], ["harnsy/reviewer"])
        self.assertEqual([(m, p) for m, p, _ in Recorder.seen],
                         [("GET", "/v1/feed.json"), ("GET", "/v1/feed.json.sig"), ("GET", "/packs/harnsy/reviewer/1.0.0.harnsy")])
        for _, _, headers in Recorder.seen:
            self.assertEqual(headers["User-Agent"], "hr-hermes/" + __version__)
            self.assertEqual(sorted(h.lower() for h in headers), ["accept-encoding", "connection", "host", "user-agent"])

    def test_a_redirect_is_not_followed(self) -> None:
        with self.assertRaises(Refusal) as got:
            HttpSource(self.base + "/moved").get("v1/feed.json", 1 << 20)
        self.assertIn("302", str(got.exception))
        self.assertEqual(len(Recorder.seen), 1)

    def test_a_missing_file_and_a_dead_address_refuse_plainly(self) -> None:
        with self.assertRaises(Refusal) as got:
            HttpSource(self.base).get("v1/nothing", 10)
        self.assertIn("404", str(got.exception))
        with self.assertRaises(Refusal) as got:
            HttpSource("http://127.0.0.1:1").get("v1/feed.json", 10)
        self.assertIn("cannot be reached", str(got.exception))

    def test_no_more_is_read_than_allowed(self) -> None:
        with self.assertRaises(Refusal) as got:
            HttpSource(self.base).get("v1/feed.json", 10)
        self.assertIn("more than 10 bytes", str(got.exception))


if __name__ == "__main__":
    unittest.main()
