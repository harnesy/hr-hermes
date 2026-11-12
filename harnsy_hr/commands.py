"""The plugin's commands, the same from a terminal and from a chat: search, show, list, hire, update, fire."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping

from . import hiring, keys, preview, search as searching
from .desk import Desk
from .errors import Refusal
from .hiring import Io
from .sources import HttpSource
from .state import State, hermes_root

SEARCH_LIMIT = 10


@dataclass
class App:
    """What a command works with; tests replace the parts."""

    environ: Mapping[str, str]
    root: Path  # the root Hermes home
    io: Io
    open_source: Callable[[str], object] = HttpSource
    now: datetime | None = None
    chat: bool = False  # the command came from a chat: nobody typed a command line

    @staticmethod
    def here(io: Io, chat: bool = False) -> "App":
        return App(environ=os.environ, root=hermes_root(), io=io, chat=chat)

    def desk(self, setup: keys.Setup) -> Desk:
        return Desk(setup, State(self.root), self.open_source(setup.base), self.now)


def run(app: App, command: str, test_catalog: bool = False, **options) -> int:
    """Runs one command. A refusal is one plain line and code 1. Which catalog a command reads is decided first,
    before a source is opened or a file is written; `list` and `fire` read none."""
    try:
        if command not in _READ_THE_CATALOG:
            return _COMMANDS[command](app, **options)
        setup = keys.setup(app.environ, test_catalog=test_catalog, chat=app.chat)
        if setup.test:
            app.io.say(keys.TEST_LINE)
        return _COMMANDS[command](app.desk(setup), app.io, **options)
    except Refusal as err:
        app.io.say(f"harnsy-hr: {err}")
    except OSError as err:
        app.io.say(f"harnsy-hr: a file could not be read or written ({type(err).__name__}: {err.strerror}: {err.filename})")
    return 1


def _search(desk: Desk, io: Io, words: str = "", department: str = "", limit: int = SEARCH_LIMIT) -> int:
    found = searching.search(desk.feed().entries, words, department)
    if not found:
        io.say("No employee matches. Try other words, or `search` alone for everyone.")
        return 0
    shown = found[:max(1, limit)]
    io.say("\n\n".join(preview.card(e) for e in shown))
    more = f" ({len(found) - len(shown)} more: add a word, or --limit {len(found)})" if len(found) > len(shown) else ""
    io.say(f"\n{len(shown)} of {len(found)}{more}. Look closer: hermes harnsy-hr show <id>")
    return 0


def _show(desk: Desk, io: Io, id: str) -> int:
    offer = desk.offer(id)
    io.say(preview.details(offer))
    io.say(f"\nHire it, at a terminal: hermes harnsy-hr hire {offer.entry.id}")
    return 0


def _list(app: App) -> int:
    state = State(app.root)
    hires = state.hires()
    if not hires:
        app.io.say("No employee is hired. Find one: hermes harnsy-hr search <words>")
        return 0
    for name, hired in sorted(hires.items()):
        gone = "" if state.profile_dir(name).is_dir() else "  (its profile is gone: `hermes harnsy-hr fire` tidies up)"
        app.io.say(preview.plain(f"{name}  {hired.get('id', '?')} {hired.get('version', '?')}{gone}"))
    app.io.say("\nTalk to one: hermes -p <name> chat")
    return 0


def _fire(app: App, name: str, yes: bool = False) -> int:
    return hiring.fire(State(app.root), app.io, name, yes=yes)


_READ_THE_CATALOG = ("search", "show", "hire", "update")
_COMMANDS = {"search": _search, "show": _show, "list": _list, "hire": hiring.hire, "update": hiring.update, "fire": _fire}
