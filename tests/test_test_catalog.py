"""A test catalog (HARNSY_HR_FEED, HARNSY_HR_PUB): it is read only when the command line says --test-catalog, never
from a chat; the question names it; plain http only to this machine; its feed number is kept apart."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from harnsy_hr import keys
from harnsy_hr.errors import Refusal
from tests.fakes import CliCase

FEED = "http://127.0.0.1:8850"
TOP = 9007199254740991  # the highest feed number there is: kept under the real key it would lock the real catalog out


class TestCatalogCase(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.both = {"HARNSY_HR_FEED": FEED, "HARNSY_HR_PUB": "t1:" + self.b64}
        self.file = self.home / "harnsy-hr" / "state.json"

    def untouched(self, before: bytes | None) -> None:
        """No catalog was opened, no child started, and the plugin's folder is as it was."""
        self.assertEqual(self.opened, [], "a catalog was opened")
        self.assertEqual(self.hermes.calls, [], "Hermes was started")
        if before is None:
            self.assertFalse((self.home / "harnsy-hr").exists(), "the plugin's folder appeared")
        else:
            self.assertEqual(self.file.read_bytes(), before)
            self.assertEqual(sorted(p.name for p in self.file.parent.iterdir()), ["state.json"])
        self.assertFalse((self.home / "profiles").exists())


class WordOnTheCommandLineTest(TestCatalogCase):
    COMMANDS = [("hire", "harnsy/reviewer", "--yes"), ("update", "reviewer", "--yes"), ("search", "review"),
                ("show", "harnsy/reviewer")]

    def refused_without_the_flag(self, environ: dict, named: str, before: bytes | None) -> None:
        self.environ = environ
        for argv in self.COMMANDS:
            self.assertEqual(self.run_cli(*argv), 1, argv)
            self.assertEqual(self.said, [f"harnsy-hr: {named}, but --test-catalog was not given: a test catalog is read "
                                         "only when the command line says so. Nothing was fetched or written. Unset "
                                         f"the variable{'s' if ' and ' in named else ''} to read hr.harnsy.dev."])
            self.untouched(before)

    def test_the_variables_alone_refuse_before_anything_is_fetched_or_written(self) -> None:
        self.refused_without_the_flag(self.both, "HARNSY_HR_FEED and HARNSY_HR_PUB are set", None)
        self.state.check_seq("c1", 76)
        self.refused_without_the_flag(self.both, "HARNSY_HR_FEED and HARNSY_HR_PUB are set", self.file.read_bytes())

    def test_each_variable_alone_refuses_too(self) -> None:
        self.refused_without_the_flag({"HARNSY_HR_FEED": FEED}, "HARNSY_HR_FEED is set", None)
        self.refused_without_the_flag({"HARNSY_HR_PUB": "t1:" + self.b64}, "HARNSY_HR_PUB is set", None)
        self.refused_without_the_flag({"HARNSY_HR_PUB": "not a key"}, "HARNSY_HR_PUB is set", None)

    def test_the_flag_without_a_variable_refuses(self) -> None:
        for environ in [{}, {"HARNSY_HR_FEED": "  ", "HARNSY_HR_PUB": ""}]:
            self.environ = environ
            for argv in self.COMMANDS:
                self.assertEqual(self.run_cli(*argv, "--test-catalog"), 1, argv)
                self.assertEqual(self.said, ["harnsy-hr: --test-catalog was given, but neither HARNSY_HR_FEED nor "
                                             "HARNSY_HR_PUB is set: there is no test catalog to read."])
                self.untouched(None)

    def test_a_chat_never_reads_a_test_catalog(self) -> None:
        self.state.check_seq("c1", 76)
        before = self.file.read_bytes()
        for environ, named in [(self.both, "HARNSY_HR_FEED and HARNSY_HR_PUB"), ({"HARNSY_HR_FEED": FEED}, "HARNSY_HR_FEED"),
                               ({"HARNSY_HR_PUB": "t1:" + self.b64}, "HARNSY_HR_PUB")]:
            self.environ = environ
            for raw in ["search review", "show harnsy/reviewer", "search --test-catalog"]:
                self.assertIn(f"harnsy-hr: A test catalog is set in this machine's environment ({named}). It is never "
                              "read from a chat; nothing was fetched.", self.run_slash(raw), raw)
                self.untouched(before)
            self.assertIn("/harnsy-hr show <id>", self.run_slash("show harnsy/reviewer --test-catalog"), "no such word in a chat")
            self.untouched(before)
            self.assertIn("No employee is hired", self.run_slash("list"), "list reads no catalog")

    def test_commands_that_read_no_catalog_work_and_take_no_flag(self) -> None:
        self.environ = self.both
        self.assertEqual(self.run_cli("list"), 0)
        self.assertEqual(self.said[0], "No employee is hired. Find one: hermes harnsy-hr search <words>")
        self.assertEqual(self.run_cli("fire", "nobody", "--yes"), 1)
        self.assertIn("no employee was hired under that profile name", self.said[0])
        self.untouched(None)
        for argv in [("list", "--test-catalog"), ("fire", "nobody", "--test-catalog")]:
            with self.assertRaises(SystemExit, msg=argv), contextlib.redirect_stderr(io.StringIO()):
                self.run_cli(*argv)

    def test_with_the_flag_every_command_says_first_that_a_test_catalog_is_in_use(self) -> None:
        self.environ = self.both
        for argv in [("search",), ("show", "harnsy/reviewer"), ("hire", "harnsy/nobody"), ("update", "nobody")]:
            self.run_cli(*argv, "--test-catalog")
            self.assertEqual(self.said[0], keys.TEST_LINE, argv)
        self.assertEqual(self.run_cli("search", "review", "--test-catalog"), 0)
        self.assertEqual(self.opened[-1], FEED)


class KeptApartTest(TestCatalogCase):
    def test_a_test_catalogs_feed_number_never_touches_the_built_in_keys(self) -> None:
        self.state.check_seq("c1", 76)  # what the real catalog left on this machine
        self.k.kid = "c1"  # the test catalog names its key as the real one is named
        self.publish("1.0.0", seq=TOP)
        self.environ = {"HARNSY_HR_FEED": FEED, "HARNSY_HR_PUB": "c1:" + self.b64}
        self.assertEqual(self.run_cli("hire", "harnsy/reviewer", "--yes", "--test-catalog"), 0)
        self.assertEqual(self.said[0], keys.TEST_LINE)
        self.assertEqual(self.hermes.calls[0][-1], "-y", "--yes with --test-catalog: both are words of the command line")
        self.assertEqual(json.loads(self.file.read_text())["seq"], {"c1": 76, "test:c1": TOP})
        self.environ = {}  # the real catalog again, a feed later
        with self.k_as_built_in("c1"):
            self.publish("1.0.0", seq=77)
            self.assertEqual(self.run_cli("search", "review"), 0, self.text)
        self.assertEqual(json.loads(self.file.read_text())["seq"], {"c1": 77, "test:c1": TOP})
        self.environ = {"HARNSY_HR_FEED": FEED, "HARNSY_HR_PUB": "c1:" + self.b64}
        self.assertEqual(self.run_cli("search", "review", "--test-catalog"), 1, "the test catalog's own number still counts")
        self.assertIn("older than one this machine has already seen (number 77, seen 9007199254740991)", self.text)

    def k_as_built_in(self, kid: str):
        return mock.patch.dict(keys.CATALOG_KEYS, {kid: self.b64}, clear=True)


class AddressTest(TestCatalogCase):
    def test_plain_http_is_taken_only_for_this_machine(self) -> None:
        for host in ["stand.example:8850", "10.0.0.5", "0.0.0.0:8850", "127.0.0.1.stand.example", "localhost.stand.example",
                     "127.0.0.2", "[::2]:8850"]:
            self.environ = {"HARNSY_HR_FEED": "http://" + host, "HARNSY_HR_PUB": "t1:" + self.b64}
            self.assertEqual(self.run_cli("hire", "harnsy/reviewer", "--yes", "--test-catalog"), 1, host)
            self.assertEqual(self.said, ["harnsy-hr: HARNSY_HR_FEED: plain http is taken only for this machine itself "
                                         "(127.0.0.1, [::1], localhost); use https for any other address."], host)
            self.untouched(None)
        for address in ["http://127.0.0.1:8850", "http://[::1]:8850/", "http://localhost:8850", "http://LOCALHOST",
                        "https://stand.example", "https://stand.example:8443/sub"]:
            got = keys.setup({"HARNSY_HR_FEED": address}, test_catalog=True)
            self.assertEqual((got.base, got.test), (address, True))

    def test_an_address_or_a_key_name_that_would_not_print_as_it_is_refuses(self) -> None:
        for bad in [{"HARNSY_HR_FEED": "http://127.0.0.1:8850/\x1b[2J"}, {"HARNSY_HR_FEED": "http://127.0.0.1:8850/a b"},
                    {"HARNSY_HR_FEED": "http://127.0.0.1:8850/\u202e"}, {"HARNSY_HR_PUB": "t\x1b1:" + self.b64},
                    {"HARNSY_HR_PUB": "t 1:" + self.b64}, {"HARNSY_HR_PUB": "k" * 17 + ":" + self.b64}]:
            with self.assertRaises(Refusal, msg=bad):
                keys.setup(bad, test_catalog=True)


class QuestionTest(TestCatalogCase):
    def test_the_question_of_hire_and_update_names_the_test_catalog(self) -> None:
        self.environ = self.both
        self.assertEqual(self.run_cli("hire", "harnsy/reviewer", "--test-catalog"), 0)
        self.publish("1.1.0", seq=8)
        self.assertEqual(self.run_cli("update", "reviewer", "--test-catalog"), 0)
        self.assertEqual(len(self.asked), 2)
        for question in self.asked:
            self.assertTrue(question.startswith("This is a TEST catalog, not hr.harnsy.dev: address http://127.0.0.1:8850, "
                                                "key t1 (from HARNSY_HR_PUB).\n"), question)
        self.assertTrue(self.asked[0].endswith("Install Reviewer as the profile «reviewer»? [y/N] "))
        self.assertTrue(self.asked[1].endswith("Update the profile «reviewer»? [y/N] "))

    def test_the_question_says_which_key_when_only_the_address_is_changed(self) -> None:
        self.environ = {"HARNSY_HR_FEED": "https://stand.example"}
        self.assertEqual(self.run_cli("hire", "harnsy/reviewer", "--test-catalog"), 0)
        self.assertTrue(self.asked[0].startswith("This is a TEST catalog, not hr.harnsy.dev: address https://stand.example, "
                                                 "key t1 (the built-in one).\n"), self.asked[0])

    def test_the_question_about_the_real_catalog_names_no_test_catalog(self) -> None:
        self.assertEqual(self.run_cli("hire", "harnsy/reviewer"), 0)
        self.assertEqual(self.asked, ["Install Reviewer as the profile «reviewer»? [y/N] "])


if __name__ == "__main__":
    unittest.main()
