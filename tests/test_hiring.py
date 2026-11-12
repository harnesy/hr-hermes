"""hire, update, fire: what is shown, what is asked, what is written, and what happens when the person says no."""

from __future__ import annotations

import json
import unittest

from harnsy_hr import hiring
from harnsy_hr.errors import Refusal
from tests.fakes import HiringCase
from tests.kit import sample


class HireTest(HiringCase):
    def hire(self, id="harnsy/reviewer", **options) -> int:
        return hiring.hire(self.desk(), self.io, id, **options)

    def test_it_shows_everything_then_asks_then_hands_the_folder_to_hermes(self) -> None:
        self.assertEqual(self.hire(), 0)
        folder = self.home / "harnsy-hr" / "profiles" / "reviewer"
        self.assertEqual(self.hermes.calls, [["profile", "install", str(folder), "--name", "reviewer"]],
                         "without -y: the person answers Hermes' own question too")
        self.assertEqual(len(self.asked), 1)
        shown = self.text[:self.text.index("Hermes Agent takes over")]
        notice = (folder / "NOTICE.md").read_text().removeprefix("# Notice\n\n")
        for want in ["Reviewer 1.0.0", "harnsy/reviewer", "Vera", "CC-BY-4.0", "SOUL.md", "skills/harnsy/race-hunt/SKILL.md",
                     "NOTICE.md", notice, str(folder), str(self.home / "profiles" / "reviewer")]:
            self.assertIn(want, shown)
        self.assertEqual(sorted(self.tree(folder)), ["NOTICE.md", "SOUL.md", "distribution.yaml",
                         "skills/harnsy/persona-casebook/SKILL.md", "skills/harnsy/persona-casebook/references/persona-casebook.md",
                         "skills/harnsy/race-hunt/SKILL.md"])
        self.assertEqual(self.state.hires(), {"reviewer": {"id": "harnsy/reviewer", "version": "1.0.0"}})
        self.assertIn("hermes -p reviewer setup", self.text)
        self.assertIn("hermes -p reviewer chat", self.text)

    def test_nothing_is_written_before_the_yes(self) -> None:
        self.answer = False
        self.assertEqual(self.hire(), 1)
        self.assertEqual(self.hermes.calls, [])
        self.assertFalse((self.home / "harnsy-hr" / "profiles").exists())
        self.assertIn("Nothing was installed", self.text)

    def test_yes_beforehand_skips_both_questions(self) -> None:
        self.assertEqual(self.hire(yes=True, alias=True, name="rev_2"), 0)
        folder = self.home / "harnsy-hr" / "profiles" / "rev_2"
        self.assertEqual(self.hermes.calls, [["profile", "install", str(folder), "--name", "rev_2", "--alias", "-y"]])
        self.assertEqual(self.asked, [])
        self.assertIn('name: "reviewer"', (folder / "distribution.yaml").read_text(), "the distribution keeps its own name")
        self.assertEqual(self.state.hires(), {"rev_2": {"id": "harnsy/reviewer", "version": "1.0.0"}})

    def test_a_no_to_hermes_own_question_is_seen_and_cleaned_up(self) -> None:
        self.hermes.decline = True
        self.assertEqual(self.hire(), 1, "the child ends with code 0 all the same")
        self.assertEqual(len(self.hermes.calls), 1)
        self.assertFalse((self.home / "harnsy-hr" / "profiles" / "reviewer").exists(), "what was built is removed")
        self.assertEqual(self.state.hires(), {})
        self.assertIn("was not installed", self.text)

    def test_an_existing_profile_stops_it(self) -> None:
        (self.home / "profiles" / "reviewer").mkdir(parents=True)
        with self.assertRaises(Refusal) as got:
            self.hire(yes=True)
        self.assertIn("already", str(got.exception))
        self.assertIn("--name", str(got.exception))
        self.assertEqual(self.hermes.calls, [])
        self.assertFalse(any("--force" in c for c in self.hermes.calls))

    def test_a_name_hermes_keeps_for_itself_asks_for_another(self) -> None:
        with self.assertRaises(Refusal) as got:
            self.hire("harnsy/test", yes=True)
        self.assertIn("--name", str(got.exception))
        for bad in ["Reviewer", "../x", "a b", "-y", "default"]:
            with self.assertRaises(Refusal):
                self.hire(name=bad, yes=True)
        self.assertEqual(self.hermes.calls, [])
        self.assertEqual(self.hire("harnsy/test", yes=True, name="tester"), 0)

    def test_a_second_hire_lives_beside_the_first(self) -> None:
        self.assertEqual(self.hire(yes=True), 0)
        first = self.tree(self.home / "profiles" / "reviewer")
        self.assertEqual(self.hire("harnsy/test", yes=True, name="tester"), 0)
        self.assertEqual(self.tree(self.home / "profiles" / "reviewer"), first)
        self.assertEqual(sorted(self.state.hires()), ["reviewer", "tester"])

    def test_a_leftover_folder_of_ours_is_rebuilt(self) -> None:
        stale = self.home / "harnsy-hr" / "profiles" / "reviewer" / "skills" / "old" / "SKILL.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale")
        self.assertEqual(self.hire(yes=True), 0)
        self.assertFalse(stale.exists())

    def test_a_refused_employee_writes_nothing(self) -> None:
        doc = json.loads(sample("reviewer")["bundle.json"])
        doc["role"]["mandate"] = "Check in with the lead every morning."
        self.publish("1.0.0", **{"bundle.json": json.dumps(doc).encode()})
        with self.assertRaises(Refusal) as got:
            self.hire(yes=True)
        self.assertIn("c2_heartbeat", str(got.exception))
        self.assertEqual(self.hermes.calls, [])
        self.assertEqual(sorted(p.name for p in (self.home / "harnsy-hr").iterdir()), ["state.json"])


class UpdateTest(HiringCase):
    def setUp(self) -> None:
        super().setUp()
        hiring.hire(self.desk(), self.io, "harnsy/reviewer", yes=True)
        self.profile = self.home / "profiles" / "reviewer"
        self.folder = self.home / "harnsy-hr" / "profiles" / "reviewer"
        (self.profile / "memories" / "MEMORY.md").write_text("mine")
        self.hermes.calls.clear(), self.said.clear()
        newer = sample("reviewer") | {"skills/race-hunt/SKILL.md": b"---\nname: race-hunt\ndescription: Find data races.\n---\nNewer.\n"}
        self.publish("1.1.0", 8, **newer)

    def test_it_verifies_again_renders_into_the_same_folder_and_lets_hermes_update(self) -> None:
        self.assertEqual(hiring.update(self.desk(), self.io, "reviewer"), 0)
        self.assertEqual(self.hermes.calls, [["profile", "update", "reviewer"]])
        self.assertIn("1.0.0", self.text)
        self.assertIn("1.1.0", self.text)
        self.assertIn(b"Newer.", (self.profile / "skills/harnsy/race-hunt/SKILL.md").read_bytes())
        self.assertIn('version: "1.1.0"', (self.folder / "distribution.yaml").read_text())
        self.assertEqual((self.profile / "memories" / "MEMORY.md").read_text(), "mine")
        self.assertEqual(self.state.hires()["reviewer"]["version"], "1.1.0")
        self.assertEqual(sorted(p.name for p in self.folder.parent.iterdir()), ["reviewer"], "no folder is left beside it")

    def test_a_skill_the_newer_version_dropped_is_named(self) -> None:
        self.publish("1.2.0", 9, **{"skills/extra/SKILL.md": b"---\nname: extra\ndescription: x\n---\nx\n"})
        self.assertEqual(hiring.update(self.desk(), self.io, "reviewer", yes=True), 0)
        self.assertNotIn("no longer has", self.text)
        self.publish("1.3.0", 10)
        self.assertEqual(hiring.update(self.desk(), self.io, "reviewer", yes=True), 0)
        self.assertIn("This version no longer has: harnsy/extra.", self.text)
        self.assertTrue((self.profile / "skills/harnsy/extra/SKILL.md").exists(), "the plugin deletes nothing in a profile")

    def test_a_no_keeps_the_old_version_everywhere(self) -> None:
        before = self.tree(self.folder)
        for decline_ours, decline_hermes in [(True, False), (False, True)]:
            self.answer, self.hermes.decline = not decline_ours, decline_hermes
            self.assertEqual(hiring.update(self.desk(), self.io, "reviewer"), 1)
            self.assertEqual(self.tree(self.folder), before)
            self.assertEqual(self.state.hires()["reviewer"]["version"], "1.0.0")
            self.assertEqual(sorted(p.name for p in self.folder.parent.iterdir()), ["reviewer"])

    def test_nothing_to_do_when_it_is_the_same(self) -> None:
        self.publish("1.0.0", 9)
        self.assertEqual(hiring.update(self.desk(), self.io, "reviewer", yes=True), 0)
        self.assertEqual(self.hermes.calls, [])
        self.assertIn("up to date", self.text)

    def test_only_what_was_hired_is_updated(self) -> None:
        (self.home / "profiles" / "mine").mkdir()
        for name in ["mine", "nobody", "../reviewer"]:
            with self.assertRaises(Refusal):
                hiring.update(self.desk(), self.io, name, yes=True)
        self.assertEqual(self.hermes.calls, [])

    def test_a_profile_someone_put_in_its_place_is_left_alone(self) -> None:
        (self.profile / "distribution.yaml").write_text('name: "reviewer"\nsource: https://example.org/other\n')
        with self.assertRaises(Refusal) as got:
            hiring.update(self.desk(), self.io, "reviewer", yes=True)
        self.assertIn("not the one this plugin installed", str(got.exception))


class FireTest(HiringCase):
    def setUp(self) -> None:
        super().setUp()
        hiring.hire(self.desk(), self.io, "harnsy/reviewer", yes=True)
        self.hermes.calls.clear()

    def test_hermes_deletes_the_profile_and_our_folder_goes_too(self) -> None:
        self.assertEqual(hiring.fire(self.state, self.io, "reviewer"), 0)
        self.assertEqual(self.hermes.calls, [["profile", "delete", "reviewer"]], "Hermes asks its own question")
        self.assertFalse((self.home / "harnsy-hr" / "profiles" / "reviewer").exists())
        self.assertEqual(self.state.hires(), {})

    def test_a_no_keeps_everything(self) -> None:
        self.hermes.decline = True
        self.assertEqual(hiring.fire(self.state, self.io, "reviewer"), 1)
        self.assertTrue((self.home / "harnsy-hr" / "profiles" / "reviewer" / "SOUL.md").exists())
        self.assertEqual(sorted(self.state.hires()), ["reviewer"])

    def test_yes_beforehand(self) -> None:
        self.assertEqual(hiring.fire(self.state, self.io, "reviewer", yes=True), 0)
        self.assertEqual(self.hermes.calls, [["profile", "delete", "reviewer", "-y"]])

    def test_only_what_was_hired_is_fired(self) -> None:
        (self.home / "profiles" / "mine").mkdir()
        for name in ["mine", "default", "../reviewer", ""]:
            with self.assertRaises(Refusal):
                hiring.fire(self.state, self.io, name, yes=True)
        self.assertEqual(self.hermes.calls, [])
        self.assertTrue((self.home / "profiles" / "mine").exists())

    def test_a_profile_already_gone_is_only_tidied_up(self) -> None:
        import shutil
        shutil.rmtree(self.home / "profiles" / "reviewer")
        self.assertEqual(hiring.fire(self.state, self.io, "reviewer"), 0)
        self.assertEqual(self.hermes.calls, [])
        self.assertEqual(self.state.hires(), {})


if __name__ == "__main__":
    unittest.main()
