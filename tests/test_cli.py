"""The commands as a person types them: `hermes harnsy-hr …` at a terminal and `/harnsy-hr …` in a chat."""

from __future__ import annotations

import argparse
import importlib.util
import socket
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from harnsy_hr import __version__, cli, keys
from tests.fakes import CliCase

ROOT = Path(__file__).parent.parent
C1 = dict(keys.CATALOG_KEYS)  # as the plugin ships it


class CliTest(CliCase):
    def test_search_show_hire_list_update_fire(self) -> None:
        self.assertEqual(self.run_cli("search", "review", "go", "code"), 0)
        self.assertIn("harnsy/reviewer  Reviewer 1.0.0  (Vera)", self.text)
        self.assertIn("Finds the race before it ships.", self.text)
        self.assertEqual(self.run_cli("search", "zeppelin"), 0)
        self.assertIn("No employee matches", self.text)
        self.assertEqual(self.run_cli("show", "harnsy/reviewer"), 0)
        self.assertIn("Licensed under CC BY 4.0", self.text)
        self.assertIn("skills/harnsy/race-hunt/SKILL.md", self.text)
        self.assertFalse((self.home / "harnsy-hr" / "profiles").exists(), "show writes no employee file")
        self.assertEqual(self.run_cli("list"), 0)
        self.assertIn("No employee is hired", self.text)
        self.assertEqual(self.run_cli("hire", "harnsy/reviewer", "--yes"), 0)
        self.assertEqual(self.run_cli("list"), 0)
        self.assertIn("reviewer  harnsy/reviewer 1.0.0", self.text)
        self.assertEqual(self.run_cli("update", "reviewer", "-y"), 0)
        self.assertIn("up to date", self.text)
        self.assertEqual(self.run_cli("fire", "reviewer", "-y"), 0)
        self.assertEqual(self.run_cli("list"), 0)
        self.assertIn("No employee is hired", self.text)

    def test_without_a_key_every_command_that_needs_the_feed_refuses_in_a_plain_sentence(self) -> None:
        for argv in [("search", "review"), ("show", "harnsy/reviewer"), ("hire", "harnsy/reviewer", "--yes")]:
            with mock.patch.dict(keys.CATALOG_KEYS, clear=True):
                self.assertEqual(self.run_cli(*argv), 1)
            self.assertEqual(self.said, ["harnsy-hr: " + keys.NO_KEY])
        self.assertEqual(self.hermes.calls, [])
        self.assertFalse((self.home / "harnsy-hr").exists())
        self.assertEqual(self.run_cli("list"), 0, "list reads no feed")

    def test_a_catalog_signed_by_another_key_than_the_built_in_one_is_refused(self) -> None:
        with mock.patch.dict(keys.CATALOG_KEYS, C1, clear=True):
            self.assertEqual(self.run_cli("search", "review"), 1)
        self.assertEqual(len(self.said), 1, "no test catalog is in use: the built-in key is")
        self.assertIn('kid "t1" is not a key this plugin knows', self.said[0])
        self.assertFalse((self.home / "harnsy-hr").exists())

    def test_a_refusal_is_one_plain_line_and_code_1(self) -> None:
        feed = self.release / "v1" / "feed.json"
        feed.write_bytes(feed.read_bytes().replace(b"Finds", b"Hides"))
        self.assertEqual(self.run_cli("hire", "harnsy/reviewer", "--yes"), 1)
        self.assertEqual(self.said, ["harnsy-hr: feed.json.sig does not verify"])
        self.assertFalse((self.home / "harnsy-hr").exists(), "nothing is written")
        self.assertFalse((self.home / "profiles").exists())

    def test_a_question_needs_a_terminal(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(Exception) as got:
                cli.ask("Install? [y/N] ")
        self.assertIn("--yes", str(got.exception))
        for typed, want in [("y", True), ("YES ", True), ("", False), ("n", False), ("yep", False)]:
            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value=typed):
                self.assertEqual(cli.ask("Install? [y/N] "), want)
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(cli.ask("Install? [y/N] "))

    def test_what_the_catalog_says_is_printed_without_control_characters(self) -> None:
        import json
        from tests.kit import sample
        doc = json.loads(sample("reviewer")["bundle.json"])
        doc["role"]["tagline"] = "Finds the race.\x1b[2J\x07 Really."
        self.publish("1.0.0", **{"bundle.json": json.dumps(doc).encode()})
        self.run_cli("search", "race")
        self.assertIn("Finds the race.[2J Really.", self.text)
        self.assertNotIn("\x1b", self.text)


class SlashTest(CliCase):
    def test_search_show_and_list_answer_in_the_chat(self) -> None:
        self.assertIn("harnsy/reviewer  Reviewer 1.0.0", self.run_slash("search review code"))
        self.assertIn("Licensed under CC BY 4.0", self.run_slash("show harnsy/reviewer"))
        self.assertIn("No employee is hired", self.run_slash("list"))
        (self.release / "v1" / "feed.json.sig").unlink()
        self.assertIn("harnsy-hr: v1/feed.json.sig", self.run_slash("show harnsy/reviewer"), "a refusal is the answer")

    def test_what_waits_for_a_person_is_handed_to_the_terminal(self) -> None:
        for raw, want in [("hire harnsy/reviewer", "hermes harnsy-hr hire harnsy/reviewer"), ("update reviewer", "hermes harnsy-hr update reviewer"),
                          ("fire reviewer", "hermes harnsy-hr fire reviewer"), ("hire  harnsy/reviewer --yes", "hermes harnsy-hr hire harnsy/reviewer"),
                          ("hire x; rm -rf ~", "hermes harnsy-hr hire <publisher>/<name>"), ("fire ../../x", "hermes harnsy-hr fire <profile name>")]:
            answer = self.run_slash(raw)
            self.assertIn(want, answer)
            self.assertIn("terminal", answer)
            self.assertNotIn("rm -rf", answer)
        self.assertEqual(self.hermes.calls, [])
        self.assertFalse((self.home / "harnsy-hr" / "profiles").exists())

    def test_every_answer_is_one_code_block_so_the_chat_makes_no_link_or_mention_of_it(self) -> None:
        import json
        from tests.kit import sample
        doc = json.loads(sample("reviewer")["bundle.json"])
        doc["role"]["tagline"] = "Finds it.\n```\n[pay here](https://elsewhere.example) @everyone `x` **now**"
        self.publish("1.0.0", **{"bundle.json": json.dumps(doc).encode()})
        for raw in ["", "list", "search review", "search zeppelin", "show harnsy/reviewer", "show harnsy/nobody",
                    "hire harnsy/reviewer", "fire `x`"]:
            answer = self.run_slash(raw)
            self.assertTrue(answer.startswith("```\n") and answer.endswith("\n```"), raw)
            self.assertNotIn("`", answer[4:-4], raw)
        self.assertIn("[pay here](https://elsewhere.example) @everyone 'x' **now**", self.run_slash("search review"))

    def test_anything_else_gets_the_usage(self) -> None:
        for raw in ["", "help", "dance", "   "]:
            self.assertIn("/harnsy-hr search <words>", self.run_slash(raw))


class Ctx:
    """The part of Hermes' plugin context this plugin may use."""

    def __init__(self) -> None:
        self.cli, self.slash, self.other = {}, {}, []

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.cli[name] = (help, setup_fn, handler_fn, description)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.slash[name] = (handler, description, args_hint)

    def __getattr__(self, name):
        self.other.append(name)
        raise AttributeError(name)


class PluginTest(unittest.TestCase):
    def load(self):
        """The plugin, imported the way Hermes imports a directory plugin."""
        parent = types.ModuleType("hermes_plugins")
        parent.__path__ = []
        spec = importlib.util.spec_from_file_location("hermes_plugins.harnsy_hr", ROOT / "__init__.py",
                                                      submodule_search_locations=[str(ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules.update({"hermes_plugins": parent, spec.name: module})
        self.addCleanup(lambda: [sys.modules.pop(m) for m in list(sys.modules) if m.startswith("hermes_plugins")])
        spec.loader.exec_module(module)
        return module

    def test_register_adds_one_cli_command_and_one_slash_command_and_opens_no_connection(self) -> None:
        ctx = Ctx()
        with mock.patch.object(socket.socket, "connect", side_effect=AssertionError("no network in register")):
            self.load().register(ctx)
        self.assertEqual(list(ctx.cli), ["harnsy-hr"])
        self.assertEqual(list(ctx.slash), ["harnsy-hr"])
        self.assertEqual(ctx.other, [], "no tool, no hook, nothing else")
        parser = argparse.ArgumentParser()
        ctx.cli["harnsy-hr"][1](parser)
        args = parser.parse_args(["hire", "harnsy/accountant", "--name", "acct", "--alias", "--yes"])
        self.assertEqual((args.harnsy_hr_command, args.id, args.name, args.alias, args.yes), ("hire", "harnsy/accountant", "acct", True, True))
        self.assertTrue(callable(ctx.cli["harnsy-hr"][2]))
        self.assertIn("search", ctx.slash["harnsy-hr"][2])

    def test_the_manifest_declares_what_the_plugin_is(self) -> None:
        manifest = (ROOT / "plugin.yaml").read_text().split("\n")
        for line in ["name: harnsy-hr", f'version: "{__version__}"', "provides_tools: []", "provides_hooks: []"]:
            self.assertIn(line, manifest)
        self.assertTrue(any(line.startswith("description: ") for line in manifest))
        self.assertFalse(any(line.startswith(("requires_env", "capabilities", "pip_dependencies", "python_dependencies")) for line in manifest))

    def test_only_hermes_public_plugin_api_is_imported(self) -> None:
        import ast
        allowed = {"hermes_constants"}  # on Hermes Agent's published plugin API list
        for file in [ROOT / "__init__.py", *sorted((ROOT / "harnsy_hr").rglob("*.py"))]:
            for node in ast.walk(ast.parse(file.read_text())):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module] if isinstance(node, ast.ImportFrom) and not node.level else []
                for name in names:
                    top = name.split(".")[0]
                    self.assertTrue(top in sys.stdlib_module_names or top in allowed | {"cryptography"}, f"{file.name} imports {name}")


if __name__ == "__main__":
    unittest.main()
