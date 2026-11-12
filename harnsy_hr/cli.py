"""`hermes harnsy-hr <search|show|hire|update|list|fire>`: the commands at a terminal."""

from __future__ import annotations

import sys

from . import commands, keys
from .errors import Refusal
from .hermes_cmd import run_hermes
from .hiring import Io

HELP = "Hire an AI employee from the catalog hr.harnsy.dev as a Hermes profile of its own"
DESCRIPTION = """Employees of the catalog hr.harnsy.dev as Hermes profiles.

  search [words]     find an employee by a role, a skill or a need
  show <id>          its card, what it needs, its files and its notice
  hire <id>          install it as a profile beside your own (asks first; Hermes asks too)
  update <name>      bring a hired employee to the catalog's current version
  list               the employees hired on this machine
  fire <name>        delete a hired employee's profile (Hermes asks to confirm)

The catalog's feed and every employee are checked against the catalog's signature on this machine before anything
is written. Network: GET to hr.harnsy.dev only, straight to it (no proxy)."""


def setup_parser(parser) -> None:
    """Builds the argparse tree of `hermes harnsy-hr`."""
    subs = parser.add_subparsers(dest="harnsy_hr_command", metavar="<command>")
    search = subs.add_parser("search", help="find an employee by a role, a skill or a need")
    search.add_argument("words", nargs="*", help="a few words, e.g.: accountant, or: review Go code")
    search.add_argument("--department", default="", help="one department, e.g. finance")
    search.add_argument("--limit", type=int, default=commands.SEARCH_LIMIT, help="how many to show (10)")
    show = subs.add_parser("show", help="an employee's card, needs, files and notice")
    show.add_argument("id", help="<publisher>/<name>, e.g. harnsy/accountant")
    hire = subs.add_parser("hire", help="install an employee as a Hermes profile of its own")
    hire.add_argument("id", help="<publisher>/<name>, e.g. harnsy/accountant")
    hire.add_argument("--name", default="", help="the profile's name (the employee's own name when left out)")
    hire.add_argument("--alias", action="store_true", help="also ask Hermes for a command named after the profile")
    update = subs.add_parser("update", help="bring a hired employee to the catalog's current version")
    fire = subs.add_parser("fire", help="delete a hired employee's profile")
    for sub in (update, fire):
        sub.add_argument("name", help="the profile's name, as `list` shows it")
    for sub in (hire, update, fire):
        sub.add_argument("-y", "--yes", action="store_true", help="say yes beforehand, to this plugin and to Hermes (scripts)")
    for sub in (search, show, hire, update):  # the commands that read the catalog
        sub.add_argument(keys.FLAG, action="store_true", help=f"test stands only: read the test catalog that "
                         f"{keys.FEED_ENV} / {keys.PUB_ENV} name instead of hr.harnsy.dev")
    subs.add_parser("list", help="the employees hired on this machine")
    parser.set_defaults(func=handle, harnsy_hr_parser=parser)


def ask(question: str) -> bool:
    """A yes/no question at the terminal. Without a terminal nothing waits: the command stops and says how to answer
    beforehand."""
    if not sys.stdin.isatty():
        raise Refusal("this step asks you a question and there is no terminal to ask at. Run it at a terminal, or "
                      "pass --yes to say yes beforehand")
    try:
        return input(question).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def run(args, app: commands.App) -> int:
    command = getattr(args, "harnsy_hr_command", None)
    test = getattr(args, "test_catalog", False)
    if command == "search":
        return commands.run(app, "search", test, words=" ".join(args.words), department=args.department, limit=args.limit)
    if command in ("show", "hire"):
        options = {"name": args.name, "alias": args.alias, "yes": args.yes} if command == "hire" else {}
        return commands.run(app, command, test, id=args.id, **options)
    if command in ("update", "fire"):
        return commands.run(app, command, test, name=args.name, yes=args.yes)
    if command == "list":
        return commands.run(app, "list")
    app.io.say(DESCRIPTION)
    return 2


def handle(args) -> int:
    """The handler Hermes calls for `hermes harnsy-hr …`; its return value is the exit code."""
    return run(args, commands.App.here(Io(run=run_hermes, ask=ask, say=print)))
