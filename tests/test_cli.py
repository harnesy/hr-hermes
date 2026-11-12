"""The commands as a person types them: `hermes harnsy-hr …` at a terminal and `/harnsy-hr …` in a chat."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import socket
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from harnsy_hr import __version__, cli, commands, keys, slash
from harnsy_hr.sources import DirSource
from tests.fakes import HiringCase

ROOT = Path(__file__).parent.parent


class CliCase(HiringCase):
    def setUp(self) -> None:
        super().setUp()
        self.environ = {"HARNSY_HR_PUB": "t1:" + base64.b64encode(self.k.pub).decode()}

    def app(self) -> commands.App:
        return commands.App(environ=self.environ, root=self.home, io=self.io, open_source=lambda base: DirSource(self.release),
                            now=self.k.now)

    def run_cli(self, *argv: str) -> int:
        parser = argparse.ArgumentParser(prog="hermes harnsy-hr")
        cli.setup_parser(parser)
        self.said.clear()
        return cli.run(parser.parse_args(argv), self.app())


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

    def test_every_command_says_first_that_a_test_catalog_is_in_use(self) -> None:
        for argv in [("search",), ("show", "harnsy/reviewer"), ("list",), ("hire", "harnsy/nobody"), ("fire", "nobody")]:
            self.run_cli(*argv)
            self.assertEqual(self.said[0], keys.TEST_LINE, argv)

    def test_without_a_key_every_command_that_needs_the_feed_refuses_in_a_plain_sentence(self) -> None:
        self.environ = {}
        for argv in [("search", "review"), ("show", "harnsy/reviewer"), ("hire", "harnsy/reviewer", "--yes")]:
            self.assertEqual(self.run_cli(*argv), 1)
            self.assertEqual(self.said, ["harnsy-hr: " + keys.NO_KEY])
        self.assertEqual(self.hermes.calls, [])
        self.assertFalse((self.home / "harnsy-hr").exists())
        self.assertEqual(self.run_cli("list"), 0, "list reads no feed")

    def test_a_refusal_is_one_plain_line_and_code_1(self) -> None:
        feed = self.release / "v1" / "feed.json"
        feed.write_bytes(feed.read_bytes().replace(b"Finds", b"Hides"))
        self.assertEqual(self.run_cli("hire", "harnsy/reviewer", "--yes"), 1)
        self.assertEqual(self.said[1:], ["harnsy-hr: feed.json.sig does not verify"])
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
    def slash(self, raw: str) -> str:
        with mock.patch.object(slash, "_app", lambda io: commands.App(self.environ, self.home, io, lambda base: DirSource(self.release), self.k.now)):
            return slash.handle(raw)

    def test_search_show_and_list_answer_in_the_chat(self) -> None:
        self.assertIn("harnsy/reviewer  Reviewer 1.0.0", self.slash("search review code"))
        self.assertIn("Licensed under CC BY 4.0", self.slash("show harnsy/reviewer"))
        self.assertIn("No employee is hired", self.slash("list"))
        (self.release / "v1" / "feed.json.sig").unlink()
        self.assertIn("harnsy-hr: v1/feed.json.sig", self.slash("show harnsy/reviewer"), "a refusal is the answer")

    def test_what_waits_for_a_person_is_handed_to_the_terminal(self) -> None:
        for raw, want in [("hire harnsy/reviewer", "hermes harnsy-hr hire harnsy/reviewer"), ("update reviewer", "hermes harnsy-hr update reviewer"),
                          ("fire reviewer", "hermes harnsy-hr fire reviewer"), ("hire  harnsy/reviewer --yes", "hermes harnsy-hr hire harnsy/reviewer"),
                          ("hire x; rm -rf ~", "hermes harnsy-hr hire <publisher>/<name>"), ("fire ../../x", "hermes harnsy-hr fire <profile name>")]:
            answer = self.slash(raw)
            self.assertIn(want, answer)
            self.assertIn("terminal", answer)
            self.assertNotIn("rm -rf", answer)
        self.assertEqual(self.hermes.calls, [])
        self.assertFalse((self.home / "harnsy-hr" / "profiles").exists())

    def test_anything_else_gets_the_usage(self) -> None:
        for raw in ["", "help", "dance", "   "]:
            self.assertIn("/harnsy-hr search <words>", self.slash(raw))


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
