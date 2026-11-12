"""The one child process this plugin starts: Hermes Agent's own `hermes profile install|update|delete`.

It is started with an argument list (never through a shell) and with the terminal the person is at, so Hermes shows
what it does and asks its own question.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from .errors import Refusal

# Settings that make Hermes approve things on its own are not handed down to the child.
_NOT_INHERITED = ("HERMES_YOLO_MODE", "HERMES_ACCEPT_HOOKS")


def find_hermes() -> str:
    found = shutil.which("hermes")
    if not found and os.path.basename(sys.argv[0]).startswith("hermes") and os.access(sys.argv[0], os.X_OK):
        found = sys.argv[0]
    if not found:
        raise Refusal("the `hermes` command is not on PATH, so the profile cannot be installed")
    return found


def run_hermes(args: list[str]) -> int:
    """Runs `hermes <args>` and returns its exit code. The code alone proves nothing: a declined install ends with 0."""
    env = {k: v for k, v in os.environ.items() if k not in _NOT_INHERITED}
    try:
        return subprocess.run([find_hermes(), *args], env=env, check=False).returncode
    except OSError as err:
        raise Refusal(f"`hermes` could not be started ({type(err).__name__})") from None
