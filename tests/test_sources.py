"""The catalog over HTTP: GET only, one address, a User-Agent that names the plugin, no redirect followed, bounded."""

from __future__ import annotations

import http.server
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from harnsy_hr import __version__, catalog, sources
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

    def test_no_proxy_is_used_whatever_the_environment_names(self) -> None:
        asked: list[bytes] = []
        proxy = answering(self, b"HTTP/1.1 200 OK\r\nContent-Length: 7\r\nConnection: close\r\n\r\nproxied", asked)
        names = ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]
        with mock.patch.dict(os.environ, {name: proxy for name in names} | {"no_proxy": "", "NO_PROXY": ""}):
            got = HttpSource(self.base).get("v1/feed.json", 1 << 20)
        self.assertEqual(got, (self.dir / "v1" / "feed.json").read_bytes())
        self.assertEqual(asked, [], "the proxy heard of the request")
        self.assertEqual([p for _, p, _ in Recorder.seen], ["/v1/feed.json"])


def answering(test: unittest.TestCase, answer: bytes, heard: list | None = None, drip: bytes = b"", every: float = 0.0) -> str:
    """The address of a server on this machine that sends `answer` to whoever asks, whatever is asked, and hangs up.
    What was asked is added to `heard`. After the answer it sends `drip` one byte at a time, `every` seconds apart."""
    listener = socket.create_server(("127.0.0.1", 0))
    test.addCleanup(listener.close)

    def serve() -> None:
        try:
            while True:
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(5)
                    asked = b""
                    while b"\r\n\r\n" not in asked and (part := conn.recv(4096)):
                        asked += part
                    if heard is not None:
                        heard.append(asked)
                    conn.sendall(answer)
                    for i in range(len(drip)):
                        time.sleep(every)
                        conn.sendall(drip[i:i + 1])
        except OSError:
            pass  # the listener is closed, or the reader hung up: the test is over

    threading.Thread(target=serve, daemon=True).start()
    return f"http://127.0.0.1:{listener.getsockname()[1]}"


class BrokenAnswerTest(unittest.TestCase):
    """What is not an answer of a web server refuses in one plain sentence, like an address nobody answers at."""

    def refused(self, base: str, rel: str) -> str:
        with self.assertRaises(Refusal) as got:
            HttpSource(base).get(rel, 1 << 20)
        return str(got.exception)

    def test_a_download_cut_short_is_refused(self) -> None:
        base = answering(self, b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\nConnection: close\r\n\r\n0123456789")
        self.assertEqual(self.refused(base, "v1/feed.json"), "v1/feed.json: the catalog cannot be reached (IncompleteRead)")

    def test_a_download_in_pieces_cut_short_is_refused(self) -> None:
        base = answering(self, b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n64\r\n0123456789")
        self.assertEqual(self.refused(base, "v1/feed.json"), "v1/feed.json: the catalog cannot be reached (IncompleteRead)")

    def test_an_answer_that_is_not_http_is_refused(self) -> None:
        base = answering(self, b"this is not a web server\r\n\r\n")
        self.assertEqual(self.refused(base, "v1/feed.json"), "v1/feed.json: the catalog cannot be reached (BadStatusLine)")

    def test_a_path_with_a_space_is_refused_before_anything_is_sent(self) -> None:
        base = answering(self, b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        self.assertEqual(self.refused(base, "v1/a b"), "v1/a b: the catalog cannot be reached (InvalidURL)")


class DeadlineTest(unittest.TestCase):
    """A whole file has one deadline, besides the wait for each piece of it."""

    HEAD = b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"

    def test_a_file_that_drips_in_is_given_up_at_the_deadline(self) -> None:
        base = answering(self, self.HEAD % 400, drip=b"x" * 400, every=0.05)  # 20 seconds, each byte well in time
        started = time.monotonic()
        with mock.patch.object(sources, "DEADLINE", 0.4, create=True), self.assertRaises(Refusal) as got:
            HttpSource(base).get("v1/feed.json", 1 << 20)
        self.assertEqual(str(got.exception), "v1/feed.json: the catalog did not send the whole file within 0.4 seconds")
        self.assertLess(time.monotonic() - started, 5)

    def test_a_file_that_comes_in_many_pieces_within_the_deadline_is_whole(self) -> None:
        body = bytes(range(256)) * 1200  # more than one piece
        base = answering(self, self.HEAD % (len(body) + 3) + body, drip=b"end", every=0.01)
        self.assertEqual(HttpSource(base).get("packs/x", 1 << 20), body + b"end")
        self.assertEqual(sources.DEADLINE, 60)


if __name__ == "__main__":
    unittest.main()
