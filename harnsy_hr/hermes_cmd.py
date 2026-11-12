"""The one child process this plugin starts: Hermes Agent's own `hermes profile install|update|delete`.

It is the Hermes that is running, started by its own interpreter: `<this Python> -P -m hermes_cli.main …`. Nothing is
looked up on PATH and nothing is taken from the current folder, so a `hermes`, a `hermes.bat` or a `hermes_cli/` that
lies where the person happens to stand is never the one started (`-P` keeps the current folder out of Python's search
for modules). It gets an argument list (never a shell) and the terminal the person is at, so Hermes shows what it does
and asks its own question.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

from .errors import Refusal

# Settings that make Hermes approve things on its own are not handed down to the child.
_NOT_INHERITED = ("HERMES_YOLO_MODE", "HERMES_ACCEPT_HOOKS")
_NOT_FOUND = "the Hermes that is running was not found; nothing was started"
_MODULE = "hermes_cli.main"


def _hermes_is_running() -> bool:
    """Whether this process is Hermes. Its package is only looked at, never imported here: an import could pick up a
    folder of that name."""
    if _MODULE.partition(".")[0] not in sys.modules:
        return False
    try:
        return importlib.util.find_spec(_MODULE) is not None
    except (ImportError, ValueError):
        return False


def hermes_argv(args: list[str]) -> list[str]:
    """The command line that starts the running Hermes with these arguments."""
    python = sys.executable or ""
    if not os.path.isabs(python) or not _hermes_is_running():
        raise Refusal(_NOT_FOUND)
    if getattr(sys, "frozen", False):  # Hermes built into one program: that program is Hermes
        return [python, *args]
    if sys.version_info < (3, 11):
        raise Refusal("this Python is older than 3.11 and cannot be told to keep the current folder out of its search "
                      "for modules; nothing was started")
    return [python, "-P", "-m", _MODULE, *args]


def run_hermes(args: list[str]) -> int:
    """Runs `hermes <args>` and returns its exit code. The code alone proves nothing: a declined install ends with 0."""
    argv = hermes_argv(args)
    env = {k: v for k, v in os.environ.items() if k not in _NOT_INHERITED}
    sys.stdout.flush()  # what was said so far is on the screen before Hermes speaks
    try:
        return subprocess.run(argv, env=env, check=False).returncode
    except OSError as err:
        raise Refusal(f"the Hermes that is running could not be started ({type(err).__name__})") from None
