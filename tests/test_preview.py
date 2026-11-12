"""What is printed to a terminal or a chat holds no character a terminal obeys and none that nobody sees."""

from __future__ import annotations

import json
import unittest

from harnsy_hr import hiring, preview
from tests.fakes import HiringCase
from tests.kit import sample

# U+202E turns the text after it around, U+2066 sets it apart, U+200B and U+00AD take no room, U+FEFF and the tag
# characters (U+E0001…) are not shown at all: Unicode category Cf, «format».
UNSEEN = "\u202e\u2066\u2069\u200b\u200d\u00ad\ufeff\u061c\u180e\U000e0001\U000e0041"


class PlainTest(unittest.TestCase):
    def test_characters_nobody_sees_and_controls_are_dropped(self) -> None:
        for c in UNSEEN:
            self.assertEqual(preview.plain(f"pay{c}roll"), "payroll", hex(ord(c)))
        for code in [*range(0x00, 0x09), *range(0x0b, 0x20), *range(0x7f, 0xa0), 0x2028, 0x2029]:
            self.assertEqual(preview.plain(f"a{chr(code)}b"), "ab", hex(code))

    def test_what_a_person_reads_stays(self) -> None:
        for text in ["Closes your month.\n\tLine two", "Zoë, naïve, Ærø", "Бухгалтер", "会計士", "- a «b» → c — d", "licence © 2026"]:
            self.assertEqual(preview.plain(text), text)

    def test_a_name_from_the_disk_stays_on_its_line(self) -> None:
        self.assertEqual(preview.one_line("a\nb\tc\x1b[2J\u202e.md"), "a b c[2J.md")


class PrintedTest(HiringCase):
    def test_a_card_is_printed_without_them(self) -> None:  # the card's line is not in SOUL.md: no scanner reads it
        doc = json.loads(sample("reviewer")["bundle.json"])
        doc["role"]["tagline"] = "Finds the race.\u202e\u200b\x9b2J Really."
        self.publish("1.0.0", **{"bundle.json": json.dumps(doc).encode()})
        offer = self.desk().offer("harnsy/reviewer")
        shown = preview.card(offer.entry) + preview.details(offer)
        self.assertIn("Finds the race.2J Really.", shown)
        self.assertEqual([hex(ord(c)) for c in shown if c in UNSEEN or c == "\x9b"], [])

    def test_file_names_read_from_the_disk_are_printed_without_them(self) -> None:
        self.assertEqual(hiring.hire(self.desk(), self.io, "harnsy/reviewer", yes=True), 0)
        folder = self.home / "harnsy-hr" / "profiles" / "reviewer"
        (folder / "left\x1b[2J\u202e\nhere.md").write_bytes(b"x")
        odd = folder / "skills" / "harnsy" / "old\x1b]0;x\x07\u200bskill"
        odd.mkdir()
        (odd / "SKILL.md").write_bytes(b"x")
        self.publish("1.1.0", seq=8)
        self.said.clear()
        self.assertEqual(hiring.update(self.desk(), self.io, "reviewer", yes=True), 0)
        self.assertIn("  gone     left[2J here.md", self.text)
        self.assertIn("  gone     skills/harnsy/old]0;xskill/SKILL.md", self.text)
        self.assertIn("This version no longer has: harnsy/old]0;xskill.", self.text)
        self.assertEqual([hex(ord(c)) for c in self.text if c in UNSEEN + "\x1b\x07"], [])


if __name__ == "__main__":
    unittest.main()
