"""The whole catalog, when one is at hand: a signed release on disk and the trees the catalog's MCP server renders
from it for Hermes Agent. Nothing of a catalog is in this repository, so the test runs only when told where they are:

    HARNSY_HR_TEST_RELEASE   a release as the site serves it (v1/feed.json, v1/feed.json.sig, the bundles)
    HARNSY_HR_TEST_PUB       <kid>:<base64 of the raw public key> the release is signed with
    HARNSY_HR_TEST_TREES     <publisher>/<name>/<name>/… : the reference tree of every employee
    HARNSY_HR_TEST_BLOCKED   optional: «<id>=<pattern>,…», the employees Hermes' scanner would block and why
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

from harnsy_hr import catalog, hermesscan, render
from harnsy_hr.sources import DirSource
from harnsy_hr.verify import parse_key

RELEASE, PUB, TREES = (os.environ.get("HARNSY_HR_TEST_" + n, "") for n in ("RELEASE", "PUB", "TREES"))


@unittest.skipUnless(RELEASE and PUB and TREES, "no catalog release at hand (see this file's head)")
class WholeCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        kid, _, b64 = PUB.partition(":")
        keys = dict([parse_key(kid, b64)])
        cls.feed, cls.employees = catalog.load_release(DirSource(Path(RELEASE)), keys, catalog.HOST, datetime.now(timezone.utc))

    def test_every_employee_renders_to_the_reference_tree(self) -> None:
        self.assertGreater(len(self.employees), 0)
        for e in self.employees:
            with self.subTest(e.entry.id):
                home = Path(TREES) / e.entry.id
                want = {p.relative_to(home).as_posix(): p.read_bytes() for p in home.rglob("*") if p.is_file()}
                got = dict(render.render(e).files)
                self.assertEqual(sorted(got), sorted(want))
                for path in got:
                    self.assertEqual(got[path], want[path], path)
        listed = {p.parent.relative_to(TREES).as_posix() for p in Path(TREES).glob("*/*/*") if p.is_dir()}
        self.assertEqual(listed, {e.entry.id for e in self.employees}, "a reference tree without an employee, or the reverse")

    def test_the_scanner_blocks_the_ones_named_and_no_other(self) -> None:
        want = dict(pair.split("=") for pair in os.environ.get("HARNSY_HR_TEST_BLOCKED", "").split(",") if pair)
        got = {}
        for e in self.employees:
            if hits := hermesscan.scan(render.render(e).soul.decode()):
                got[e.entry.id] = ",".join(hits)
        self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()
