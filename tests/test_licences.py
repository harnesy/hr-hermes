"""The licences that travel with the code: ours, and Hermes Agent's for the patterns copied from it."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


class LicencesTest(unittest.TestCase):
    def test_the_code_is_mit_in_our_name(self) -> None:
        text = (ROOT / "LICENSE").read_text()
        self.assertTrue(text.startswith("MIT License\n\nCopyright (c) 2026 Pavel Buchnev (harnsy)\n"))

    def test_hermes_agents_notice_travels_with_the_copied_patterns(self) -> None:
        beside = (ROOT / "harnsy_hr" / "hermesscan" / "LICENSE").read_text()
        self.assertTrue(beside.startswith("MIT License\n\nCopyright (c) 2025 Nous Research\n"))
        self.assertIn("The above copyright notice and this permission notice shall be included", beside)
        self.assertIn(beside, (ROOT / "THIRD_PARTY_LICENSES").read_text(), "the full text, in step with the file beside the module")
        notice = (ROOT / "NOTICE").read_text()
        for want in ["Hermes Agent (github.com/NousResearch/hermes-agent)", "Nous Research (MIT)", "harnsy_hr/hermesscan",
                     "THIRD_PARTY_LICENSES"]:
            self.assertIn(want, notice)

    def test_the_readme_says_what_a_person_must_know_before_installing(self) -> None:
        readme = (ROOT / "README.md").read_text()
        for want in ["https://hr.harnsy.dev` only", "User-Agent: hr-hermes/<version>", "~/.hermes/harnsy-hr/",
                     "~/.hermes/profiles/<name>/", "hermes profile install", "never runs", "never fetches or replaces its own code",
                     "This project is not affiliated with or endorsed by OpenClaw, Nous Research (Hermes Agent), Anthropic, "
                     "OpenAI or the\nMCP project; their names are used only to say what it works with."]:
            self.assertIn(want, readme)

    def test_no_real_employee_text_is_in_the_repository(self) -> None:
        employees = sorted(p.relative_to(ROOT / "tests" / "testdata" / "employees").as_posix()
                           for p in (ROOT / "tests" / "testdata" / "employees").glob("*/*"))
        self.assertEqual(employees, ["harnsy/sample-plain", "harnsy/sample-scripts", "harnsy/sample-skills", "octo/sample-guest"],
                         "only the four made-up employees")


if __name__ == "__main__":
    unittest.main()
