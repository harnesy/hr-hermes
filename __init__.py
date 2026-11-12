"""harnsy-hr: a Hermes Agent plugin that installs an employee from the signed catalog hr.harnsy.dev as a Hermes
profile of its own.

It adds one CLI command (`hermes harnsy-hr …`) and one slash command (`/harnsy-hr …`). It registers no tools and no
hooks, so the model never calls it: it runs only when a person does. Loading it opens no network connection.
"""

from __future__ import annotations


def register(ctx) -> None:
    """Called by Hermes once at startup."""
    from .harnsy_hr import cli, slash

    ctx.register_cli_command(name="harnsy-hr", help=cli.HELP, setup_fn=cli.setup_parser, handler_fn=cli.handle,
                             description=cli.DESCRIPTION)
    ctx.register_command("harnsy-hr", handler=slash.handle, description=slash.DESCRIPTION, args_hint=slash.ARGS_HINT)
