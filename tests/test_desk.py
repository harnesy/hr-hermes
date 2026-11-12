"""The front desk: a catalog key is needed, an older feed is refused, an employee Hermes would block is not offered."""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from harnsy_hr import keys
from harnsy_hr.desk import Desk
from harnsy_hr.errors import Refusal
from harnsy_hr.sources import DirSource
from harnsy_hr.state import State
from tests.kit import Kit, sample


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.k = Kit()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.release, self.home = Path(tmp.name) / "release", Path(tmp.name) / "home"
        self.state = State(self.home)

    def desk(self, known=None) -> Desk:
        setup = keys.Setup(base="", keys=self.k.keys if known is None else known, test=False)
        return Desk(setup, self.state, DirSource(self.release), self.k.now)

    def publish(self, seq: int = 7, packs=None, **doc) -> None:
        packs = packs or [self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer") | doc)]
        self.k.release(self.release, packs, lambda f: f.update(seq=seq))


class SeqTest(Case):
    def test_an_older_feed_is_refused_and_the_highest_is_remembered(self) -> None:
        self.publish(7)
        self.assertEqual(self.desk().feed().seq, 7)
        self.publish(9)
        self.assertEqual(self.desk().feed().seq, 9)
        self.assertEqual(json.loads((self.home / "harnsy-hr" / "state.json").read_text())["seq"], {"t1": 9})
        self.publish(8)
        with self.assertRaises(Refusal) as got:
            self.desk().feed()
        self.assertIn("older than one this machine has already seen (number 8, seen 9)", str(got.exception))
        self.publish(9)
        self.assertEqual(self.desk().feed().seq, 9, "the same feed again is fine")

    def test_a_feed_that_does_not_verify_is_not_remembered(self) -> None:
        self.publish(50)
        feed = self.release / "v1" / "feed.json"
        feed.write_bytes(feed.read_bytes().replace(b"Finds", b"Hides"))
        with self.assertRaises(Refusal):
            self.desk().feed()
        self.assertFalse((self.home / "harnsy-hr").exists(), "nothing is written for a feed that is refused")

    def test_each_key_counts_for_itself(self) -> None:
        self.publish(7)
        self.desk().feed()
        self.state.check_seq("c1", 3)
        self.state.check_seq("c1", 3)
        with self.assertRaises(Refusal):
            self.state.check_seq("c1", 2)

    def test_a_damaged_state_file_stops_the_work(self) -> None:
        self.publish(7)
        (self.home / "harnsy-hr").mkdir(parents=True)
        for bad in ["{", "[]", '{"seq": 5}']:
            (self.home / "harnsy-hr" / "state.json").write_text(bad)
            with self.assertRaises(Refusal) as got:
                self.desk().feed()
            self.assertIn("damaged", str(got.exception))


class KeyTest(Case):
    def test_without_a_key_built_in_nothing_is_fetched(self) -> None:
        self.assertEqual(keys.setup({}).keys, {}, "the slot of the real key is empty in this version")
        self.publish()
        with self.assertRaises(Refusal) as got:
            self.desk(known={}).feed()
        self.assertIn("holds no catalog key yet", str(got.exception))

    def test_a_stand_names_its_address_and_key(self) -> None:
        b64 = base64.b64encode(self.k.pub).decode()
        got = keys.setup({"HARNSY_HR_FEED": "http://127.0.0.1:8850/", "HARNSY_HR_PUB": "t1:" + b64})
        self.assertEqual((got.base, got.keys, got.test), ("http://127.0.0.1:8850/", {"t1": self.k.pub}, True))
        plain = keys.setup({})
        self.assertEqual((plain.base, plain.test), ("https://hr.harnsy.dev", False))
        self.assertTrue(keys.setup({"HARNSY_HR_FEED": "https://stand.example"}).test)
        for bad in [{"HARNSY_HR_PUB": "t1"}, {"HARNSY_HR_PUB": ":" + b64}, {"HARNSY_HR_PUB": "t1:short"},
                    {"HARNSY_HR_FEED": "ftp://x"}, {"HARNSY_HR_FEED": "stand.example"},
                    {"HARNSY_HR_FEED": "https://user:pw@stand.example"}, {"HARNSY_HR_FEED": "https://stand.example/?a=b"}]:
            with self.assertRaises(Refusal, msg=bad):
                keys.setup(bad)


class OfferTest(Case):
    def test_an_employee_is_offered_with_its_files(self) -> None:
        self.publish()
        offer = self.desk().offer("harnsy/reviewer")
        self.assertEqual(offer.tree.name, "reviewer")
        self.assertEqual(offer.paths(), ["NOTICE.md", "SOUL.md", "distribution.yaml", "skills/harnsy/persona-casebook/SKILL.md",
                                         "skills/harnsy/persona-casebook/references/persona-casebook.md",
                                         "skills/harnsy/race-hunt/SKILL.md"])

    def test_what_is_asked_for_must_be_an_id_the_catalog_has(self) -> None:
        self.publish()
        for id, want in [("harnsy/nobody", "no employee harnsy/nobody"), ("../../etc", "not an id"), ("reviewer", "not an id")]:
            with self.assertRaises(Refusal) as got:
                self.desk().offer(id)
            self.assertIn(want, str(got.exception))

    def test_an_employee_hermes_would_block_is_not_offered(self) -> None:
        doc = json.loads(sample("reviewer")["bundle.json"])
        doc["role"]["prompt"] = "Pretend to be a customer when you test the form."
        self.publish(**{"bundle.json": json.dumps(doc).encode()})
        with self.assertRaises(Refusal) as got:
            self.desk().offer("harnsy/reviewer")
        self.assertIn("role_pretend", str(got.exception))
        self.assertIn("Nothing was installed", str(got.exception))


if __name__ == "__main__":
    unittest.main()
