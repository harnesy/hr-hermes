"""`/harnsy-hr search|show|list` inside a chat.

A slash command runs in the process that serves the chat, where nobody sits at a terminal. So only what reads is done
here; for hire, update and fire the answer is the command to run at a terminal: they ask a person, and nothing that
waits for a person may run here.

A chat shows an answer as Markdown, and the text of a card or a notice is its publisher's. So every answer goes out as
one code block: a link, a mention or a heading written there is shown as it is written and not made by the bot.
"""

from __future__ import annotations

from . import commands, grammar
from .errors import Refusal
from .hiring import Io

DESCRIPTION = "Find employees of the catalog hr.harnsy.dev; hiring is done at a terminal"
ARGS_HINT = "search <words> | show <id> | list"
USAGE = """/harnsy-hr search <words>   find an employee by a role, a skill or a need
/harnsy-hr show <id>        its card, what it needs, its files and its notice
/harnsy-hr list             the employees hired on this machine
Hiring, updating and firing ask you questions, so they run at a terminal:
  hermes harnsy-hr hire <id>  |  hermes harnsy-hr update <name>  |  hermes harnsy-hr fire <name>"""


def _no_terminal(*_args) -> bool:
    raise Refusal("this step needs a terminal")


def _app(io: Io) -> commands.App:
    return commands.App.here(io, chat=True)


def _at_a_terminal(command: str, rest: list[str]) -> str:
    """The terminal command for a step that asks a person. What was typed is repeated only when it has the form of an
    id or a profile name."""
    target = rest[0] if rest else ""
    if command == "hire":
        target = target if grammar.is_id(target) else "<publisher>/<name>"
    else:
        target = target if target and not grammar.profile_name_fault(target) else "<profile name>"
    return (f"`{command}` asks you questions and then lets Hermes' own `hermes profile` command ask too, so it runs "
            f"at a terminal, not in a chat. Run:\n  hermes harnsy-hr {command} {target}")


def handle(raw_args: str) -> str:
    """The handler Hermes calls with everything typed after /harnsy-hr; what it returns is shown in the chat."""
    return "```\n" + _answer(raw_args).replace("`", "'") + "\n```"  # no backtick inside: the block cannot be left


def _answer(raw_args: str) -> str:
    words = (raw_args or "").split()
    command, rest = (words[0].lower(), words[1:]) if words else ("", [])
    if command in ("hire", "update", "fire"):
        return _at_a_terminal(command, rest)
    said: list[str] = []
    app = _app(Io(run=_no_terminal, ask=_no_terminal, say=said.append))
    if command == "search":
        commands.run(app, "search", words=" ".join(rest))
    elif command == "show" and len(rest) == 1:
        commands.run(app, "show", id=rest[0])
    elif command == "list" and not rest:
        commands.run(app, "list")
    else:
        return USAGE
    return "\n".join(said)
