"""The child process: the Hermes that is running, by its own interpreter, with an argument list. No lookup on PATH,
nothing of the current folder, never a shell; approve-everything settings are not inherited."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harnsy_hr import hermes_cmd, hermesscan
from harnsy_hr.errors import Refusal

# A stand-in for Hermes' own `hermes_cli.main`: says what it was started with, and ends with 7.
STUB = """import json, os, sys
with open(os.path.join(os.environ["OUT"], "seen.json"), "w") as f:
    json.dump({"args": sys.argv[1:], "env": dict(os.environ), "file": __file__}, f)
sys.exit(7)
"""
# What someone left in the folder the person stands in: each of them leaves a mark when it runs.
PLANTED_SH = "#!/bin/sh\ntouch \"$OUT/planted\"\n"
PLANTED_PY = "import os\nopen(os.path.join(os.environ['OUT'], 'planted'), 'w').close()\n"


class Case(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.real, self.cwd = self.dir / "real", self.dir / "cwd"
        (self.real / "hermes_cli").mkdir(parents=True)
        (self.real / "hermes_cli" / "__init__.py").write_text("")
        (self.real / "hermes_cli" / "main.py").write_text(STUB)
        (self.cwd / "hermes_cli").mkdir(parents=True)
        for name in ("__init__.py", "main.py"):
            (self.cwd / "hermes_cli" / name).write_text(PLANTED_PY)
        for name in ("hermes", "hermes.bat", "hermes.cmd"):
            (self.cwd / name).write_text(PLANTED_SH)
            (self.cwd / name).chmod(0o755)
        before = os.getcwd()
        self.addCleanup(os.chdir, before)
        os.chdir(self.cwd)
        self.env = {"PATH": f".{os.pathsep}{os.pathsep}{self.cwd}{os.pathsep}/usr/bin{os.pathsep}/bin", "OUT": str(self.dir),
                    "PYTHONPATH": str(self.real), "HERMES_YOLO_MODE": "1", "HERMES_ACCEPT_HOOKS": "1",
                    "HERMES_HOME": "/somewhere"}

    def hermes_runs(self) -> None:
        """Makes this process look like Hermes: its `hermes_cli` is loaded, from a place that is not the current folder."""
        saved = {name: sys.modules.pop(name) for name in list(sys.modules) if name.split(".")[0] == "hermes_cli"}
        sys.path.insert(0, str(self.real))
        import hermes_cli  # noqa: F401  (the stand-in)

        def undo() -> None:
            sys.path.remove(str(self.real))
            for name in [n for n in sys.modules if n.split(".")[0] == "hermes_cli"]:
                del sys.modules[name]
            sys.modules.update(saved)
        self.addCleanup(undo)

    def seen(self) -> dict:
        return json.loads((self.dir / "seen.json").read_text())


class ArgvTest(Case):
    def test_the_running_hermes_is_started_by_its_interpreter_and_nothing_of_the_folder_or_path(self) -> None:
        self.hermes_runs()
        with mock.patch.dict(os.environ, self.env, clear=True):
            argv = hermes_cmd.hermes_argv(["profile", "list"])
        self.assertEqual(argv, [sys.executable, "-P", "-m", "hermes_cli.main", "profile", "list"])
        self.assertTrue(os.path.isabs(argv[0]))
        self.assertFalse(Path(argv[0]).is_relative_to(self.cwd))

    def test_a_folder_named_hermes_cli_is_not_taken_for_the_running_hermes(self) -> None:
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(sys, "path", ["", *sys.path]):
            with self.assertRaises(Refusal) as got:
                hermes_cmd.run_hermes(["profile", "list"])
        self.assertEqual(str(got.exception), "the Hermes that is running was not found; nothing was started")
        self.assertNotIn("hermes_cli", sys.modules, "the folder's package was not even imported")
        self.assertFalse((self.dir / "planted").exists())
        self.assertFalse((self.dir / "seen.json").exists())

    def test_an_interpreter_without_a_full_path_starts_nothing(self) -> None:
        self.hermes_runs()
        for exe in ["", "python", "./python", "hermes.bat"]:
            with mock.patch.object(sys, "executable", exe), self.assertRaises(Refusal) as got:
                hermes_cmd.hermes_argv(["profile", "list"])
            self.assertIn("was not found; nothing was started", str(got.exception))

    def test_a_python_that_cannot_leave_the_current_folder_out_starts_nothing(self) -> None:
        self.hermes_runs()
        with mock.patch.object(sys, "version_info", (3, 10, 14)), self.assertRaises(Refusal) as got:
            hermes_cmd.hermes_argv(["profile", "list"])
        self.assertIn("older than 3.11", str(got.exception))
        self.assertIn("nothing was started", str(got.exception))

    def test_a_hermes_built_into_one_program_is_started_as_that_program(self) -> None:
        self.hermes_runs()
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual(hermes_cmd.hermes_argv(["profile", "list"]), [sys.executable, "profile", "list"])


class RunTest(Case):
    def test_arguments_reach_hermes_one_by_one_and_its_code_comes_back(self) -> None:
        self.hermes_runs()
        odd = "a b; touch " + str(self.dir / "pwned") + " $(id) `id` | x"
        with mock.patch.dict(os.environ, self.env, clear=True):
            code = hermes_cmd.run_hermes(["profile", "install", odd, "--name", "x"])
        self.assertEqual(code, 7)
        seen = self.seen()
        self.assertEqual(seen["args"], ["profile", "install", odd, "--name", "x"])
        self.assertFalse((self.dir / "pwned").exists())
        self.assertEqual(seen["env"]["HERMES_HOME"], "/somewhere")
        self.assertNotIn("HERMES_YOLO_MODE", seen["env"])
        self.assertNotIn("HERMES_ACCEPT_HOOKS", seen["env"])

    def test_what_lies_in_the_current_folder_is_not_started_and_not_imported(self) -> None:
        self.hermes_runs()
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(hermes_cmd.run_hermes(["profile", "list"]), 7)
        self.assertFalse((self.dir / "planted").exists(), "a hermes, hermes.bat or hermes_cli/ of the folder ran")
        self.assertEqual(self.seen()["file"], str(self.real / "hermes_cli" / "main.py"))

    def test_the_code_never_builds_a_shell_string_and_never_asks_path(self) -> None:
        root = Path(__file__).parent.parent
        for file in [root / "__init__.py", *sorted((root / "harnsy_hr").rglob("*.py"))]:
            text = file.read_text()
            for never in ["os.system", "os.popen", "shell=True", "eval(", "exec(", "pty.spawn", "shutil.which"]:
                self.assertNotIn(never, text, f"{file.name} must not use {never}")
            if "subprocess" in text:
                self.assertEqual(file.name, "hermes_cmd.py", "one child process, in one place")
            hidden = [hex(ord(c)) for c in text if c in hermesscan.INVISIBLE or c in "\u2028\u2029"]
            self.assertEqual(hidden, [], f"{file.name} holds a character nobody sees: write it as an escape")


if __name__ == "__main__":
    unittest.main()
