"""An employee renders to a Hermes profile distribution: byte for byte the tree under testdata/golden/hermes."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from harnsy_hr import catalog, hermesscan, notice, render
from harnsy_hr.errors import Refusal
from harnsy_hr.sources import DirSource
from harnsy_hr.types import Doc, Employee, Entry, Manifest
from tests.kit import HOST, TESTDATA, Kit, source


def staff() -> list[Employee]:
    """The release of the made-up employees under testdata/employees."""
    k = Kit()
    with tempfile.TemporaryDirectory() as tmp:
        k.release(Path(tmp), k.catalog(TESTDATA / "employees"))
        return catalog.load_release(DirSource(Path(tmp)), k.keys, HOST, k.now)[1]


def worker(publisher: str, publisher_name: str, licence: str, files=()) -> Employee:
    """A made-up employee with the fields a notice reads."""
    entry = Entry.read({"id": publisher + "/sample", "version": "1.0.0", "title": "Sample", "publisher": publisher,
                        "publisher_name": publisher_name, "published": "2026-03-04"})
    return Employee(entry, Manifest("", 1, entry.id, "1.0.0", "employee", "", {}), "", Doc(license=licence),
                    dict.fromkeys(files, b"x"))


class GoldenTest(unittest.TestCase):
    def test_every_test_employee_renders_to_its_golden_tree(self) -> None:
        employees = staff()
        self.assertEqual(len(employees), 4)
        for e in employees:
            with self.subTest(e.entry.id):
                tree = render.render(e)
                want = source(TESTDATA / "golden" / "hermes" / e.entry.id.replace("/", "-"))
                got = dict(tree.files)
                self.assertEqual(len(got), len(tree.files), "a path is in the tree twice")
                self.assertEqual(sorted(got), sorted(want))
                self.assertEqual([p for p, _ in tree.files], sorted(got), "files are in path order")
                for path, content in got.items():
                    self.assertEqual(content, want[path], path + " differs from the golden file")

    def test_the_shape_of_a_distribution(self) -> None:
        for e in staff():
            with self.subTest(e.entry.id):
                tree = render.render(e)
                publisher, name = e.entry.id.split("/")
                files = {p.removeprefix(name + "/"): b for p, b in tree.files}
                self.assertTrue(all(p.startswith(name + "/") for p, _ in tree.files))
                for never in ["config.yaml", ".env", "mcp.json", "cron/jobs.json", "auth.json"]:
                    self.assertNotIn(never, files, "it is the person's")
                self.assertFalse(any("avatar" in p for p in files))
                soul = files["SOUL.md"].decode()
                for want in [e.doc.character, e.doc.mandate, e.doc.prompt, "AI agent"]:
                    self.assertIn(want, soul)
                last = soul.rstrip("\n").split("\n")[-1]
                self.assertIn(e.entry.cv_url, last)
                self.assertIn(e.entry.title + " " + e.entry.version, last)
                self.assertEqual(files["NOTICE.md"].decode(), "# Notice\n\n" + tree.notice)
                self.assertEqual(hermesscan.scan(soul), [])
                manifest = files["distribution.yaml"].decode().split("\n")
                self.assertIn(f'name: "{name}"', manifest)
                self.assertIn(f'version: "{e.entry.version}"', manifest)
                self.assertFalse(any(line.startswith(("env_requires", "distribution_owned")) for line in manifest))
                for path, content in e.files.items():
                    if path.startswith("skills/"):
                        self.assertEqual(files["skills/" + publisher + "/" + path.removeprefix("skills/")], content)
                wrapper = files.get(f"skills/{publisher}/persona-casebook/SKILL.md")
                casebook = e.files.get("docs/persona-casebook.md")
                self.assertEqual(wrapper is None, casebook is None)
                if casebook is not None:
                    self.assertEqual(files[f"skills/{publisher}/persona-casebook/references/persona-casebook.md"], casebook)
                    self.assertRegex(wrapper.decode(), r'(?s)\A---\nname: persona-casebook\ndescription: "[^"\n]{20,1024}"\n---\n\n.+')
                    self.assertIn("`persona-casebook`", soul)
                for sealed in ["A made-up desk manual", "nodes", "[S1]"]:
                    self.assertNotIn(sealed, b"\n".join(files.values()).decode(), "sources and harnsy Max needs stay sealed")

    def test_a_skill_that_takes_the_casebooks_place_is_refused(self) -> None:
        e = worker("harnsy", "", "CC-BY-4.0", ["docs/persona-casebook.md", "skills/persona-casebook/SKILL.md"])
        with self.assertRaises(Refusal):
            render.render(e)


class YamlTest(unittest.TestCase):
    def test_a_value_is_one_quoted_line(self) -> None:
        for text, want in [("plain", '"plain"'), ('say "hi"', r'"say \"hi\""'), ("a\\b", r'"a\\b"'), ("a\nb", r'"a\nb"'),
                           ("tab\there", r'"tab\there"'), ("no", '"no"'), ("1.0", '"1.0"'), ("<b> & 'c'", "\"<b> & 'c'\""),
                           ("«ёж» — 日本", '"«ёж» — 日本"'), ("a\u2028b\u2029c", r'"a\u2028b\u2029c"'), ("\x01\x7f", '"\\u0001\x7f"'),
                           ("\b\f\r", r'"\b\f\r"')]:
            self.assertEqual(render.yaml_string(text), want)

    def test_one_line(self) -> None:
        self.assertEqual(render.one_line("  a \n b\t\tc\u00a0d\u2003e  "), "a b c d e")
        self.assertEqual(render.one_line("a\x1fb"), "a\x1fb", "only what the reference reads as a space is one")


class NoticeTest(unittest.TestCase):
    """Who is credited and how, by publisher and licence. The wording is the lawyer's."""

    TAIL = " Source: https://hr.harnsy.dev/e/%s/sample. Changes: rendered for a test. Provided as is, without warranty of any kind (see the licence)."
    CC_BY = " Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)."
    CC0 = " Dedicated to the public domain under CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/)."
    NONE = " No licence is stated for this employee: do not copy or redistribute it."
    LISTED = "\nhr.harnsy.dev lists this work; it is not made or endorsed by harnsy.\n"
    OURS = "\nThe names and logos «harnsy» and «hr.harnsy.dev», and the picture of this employee (not included here), are not covered by this licence.\n"
    THEIRS = "\nThe names and logos «harnsy» and «hr.harnsy.dev» are not covered by this licence.\n"

    def test_wording(self) -> None:
        ours, theirs = self.TAIL % "harnsy" + "\n" + self.OURS, self.TAIL % "octo" + "\n" + self.LISTED + self.THEIRS
        for name, e, want in [
            ("own, CC BY: the copyright notice", worker("harnsy", "harnsy", "CC-BY-4.0"),
             "Sample 1.0.0 by harnsy (Pavel Buchnev), © 2026 Pavel Buchnev (harnsy)." + self.CC_BY + ours),
            ("own, CC0: no copyright notice beside a dedication", worker("harnsy", "harnsy", "CC0-1.0"),
             "Sample 1.0.0 by harnsy (Pavel Buchnev)." + self.CC0 + ours),
            ("own, no licence: all rights reserved", worker("harnsy", "harnsy", ""),
             "Sample 1.0.0 by harnsy (Pavel Buchnev), © 2026 Pavel Buchnev (harnsy)." + self.NONE + ours),
            ("another publisher, CC BY: its copyright notice, not ours", worker("octo", "Octo Press", "CC-BY-4.0"),
             "Sample 1.0.0 by Octo Press, © 2026 Octo Press, published on hr.harnsy.dev." + self.CC_BY + theirs),
            ("another publisher, CC0", worker("octo", "Octo Press", "CC0-1.0"), "Sample 1.0.0 by Octo Press." + self.CC0 + theirs),
            ("another publisher without a display name", worker("octo", "", "CC-BY-4.0"),
             "Sample 1.0.0 by octo, © 2026 octo, published on hr.harnsy.dev." + self.CC_BY + theirs),
        ]:
            with self.subTest(name):
                self.assertEqual(notice.notice(e, "rendered for a test"), want)

    def test_the_note_is_marked_as_the_publishers(self) -> None:
        for publisher, want in [("harnsy", "\nNote from harnsy: Keep the names.\n"), ("octo", "\nNote from the publisher: Keep the names.\n")]:
            e = worker(publisher, "", "CC-BY-4.0")
            e.entry.license_note = "Keep the names."
            self.assertIn(want, notice.notice(e, "x"))

    def test_it_points_at_skill_licences(self) -> None:
        pointer = ("\nSome skills carry another licence for the parts adapted from other works or for their scripts (for example MIT): "
                   "it is the `LICENSE` file in that skill's folder, and it applies to those parts (the bundle's licence: %s).\n")
        for name, licence, files, want in [
            ("a skill with a LICENSE under a plain expression", "CC-BY-4.0", ["skills/a/SKILL.md", "skills/a/LICENSE"], True),
            ("a skill with a LICENSE under AND", "CC-BY-4.0 AND MIT", ["skills/a/LICENSE"], True),
            ("AND without a LICENSE file", "CC-BY-4.0 AND MIT", ["skills/a/SKILL.md"], False),
            ("a LICENSE deeper in a skill is not the skill's own", "CC-BY-4.0", ["skills/a/references/LICENSE"], False),
            ("no skills", "CC-BY-4.0", [], False),
        ]:
            with self.subTest(name):
                self.assertEqual(pointer % licence in notice.notice(worker("harnsy", "", licence, files), "x"), want)

    def test_a_credit_without_a_year(self) -> None:
        e = worker("harnsy", "", "CC-BY-4.0")
        e.entry.published = ""
        self.assertIn("by harnsy (Pavel Buchnev), © Pavel Buchnev (harnsy).", notice.credit(e, "x"))

    def test_the_notices_of_the_test_employees(self) -> None:
        notices = {e.entry.id: render.render(e).notice for e in staff()}
        self.assertIn("- A Made-up Guide to Shelves — Example Author, https://example.org/shelves, CC-BY-4.0, modified",
                      notices["harnsy/sample-skills"])
        self.assertIn("- Loan Desk Notes, https://example.org/loans, CC0-1.0, not modified", notices["harnsy/sample-skills"])
        self.assertIn("Note from harnsy: No rights in the names of the people mentioned are granted or implied.",
                      notices["harnsy/sample-scripts"])
        for never in ["Pavel Buchnev", "CC BY 4.0", "©", "picture"]:
            self.assertNotIn(never, notices["octo/sample-guest"])
        self.assertTrue(all(re.search(r"Changes: rendered for hermes\.", n) for n in notices.values()))


if __name__ == "__main__":
    unittest.main()
