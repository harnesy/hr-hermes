"""The child process: `hermes` with an argument list, never a shell; approve-everything settings are not inherited."""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harnsy_hr import hermes_cmd, hermesscan
from harnsy_hr.errors import Refusal

FAKE = """#!/bin/sh
printf '%s\\n' "$@" > "$OUT/args"
env > "$OUT/env"
exit 7
"""


class RunTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        exe = self.dir / "bin" / "hermes"
        exe.parent.mkdir()
        exe.write_text(FAKE)
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)

    def test_arguments_reach_hermes_one_by_one_and_its_code_comes_back(self) -> None:
        env = {"PATH": f"{self.dir / 'bin'}:/usr/bin:/bin", "OUT": str(self.dir), "HERMES_YOLO_MODE": "1",
               "HERMES_ACCEPT_HOOKS": "1", "HERMES_HOME": "/somewhere"}
        odd = "a b; touch " + str(self.dir / "pwned") + " $(id) `id` | x"
        with mock.patch.dict(os.environ, env, clear=True):
            code = hermes_cmd.run_hermes(["profile", "install", odd, "--name", "x"])
        self.assertEqual(code, 7)
        self.assertEqual((self.dir / "args").read_text().split("\n")[:-1], ["profile", "install", odd, "--name", "x"])
        self.assertFalse((self.dir / "pwned").exists())
        child = (self.dir / "env").read_text()
        self.assertIn("HERMES_HOME=/somewhere", child)
        self.assertNotIn("HERMES_YOLO_MODE", child)
        self.assertNotIn("HERMES_ACCEPT_HOOKS", child)

    def test_without_hermes_on_path_it_says_so(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": str(self.dir)}, clear=True), mock.patch("sys.argv", ["python"]):
            with self.assertRaises(Refusal) as got:
                hermes_cmd.run_hermes(["profile", "list"])
        self.assertIn("not on PATH", str(got.exception))

    def test_the_code_never_builds_a_shell_string(self) -> None:
        root = Path(__file__).parent.parent
        for file in [root / "__init__.py", *sorted((root / "harnsy_hr").rglob("*.py"))]:
            text = file.read_text()
            for never in ["os.system", "os.popen", "shell=True", "eval(", "exec(", "pty.spawn"]:
                self.assertNotIn(never, text, f"{file.name} must not use {never}")
            if "subprocess" in text:
                self.assertEqual(file.name, "hermes_cmd.py", "one child process, in one place")
            hidden = [hex(ord(c)) for c in text if c in hermesscan.INVISIBLE or c in "\u2028\u2029"]
            self.assertEqual(hidden, [], f"{file.name} holds a character nobody sees: write it as an escape")


if __name__ == "__main__":
    unittest.main()
