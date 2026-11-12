"""hire, update, fire: an employee becomes a Hermes profile through Hermes' own `hermes profile …`.

Nothing is written before the person says yes. The distribution folder is built in the plugin's own folder under the
Hermes home and stays there: `hermes profile update` reads it again. Hermes then asks its own question; its exit code
proves nothing (a declined install ends with 0), so the result is read from the profile folder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import folders, grammar, preview
from .desk import Desk, Offer
from .errors import Refusal
from .state import State


@dataclass
class Io:
    """How the flows reach Hermes and the person."""

    run: Callable[[list[str]], int]  # runs `hermes <args>` at the person's terminal
    ask: Callable[[str], bool]  # a yes/no question to the person
    say: Callable[[str], None]


def _profile_name(name: str, hint: str) -> str:
    if fault := grammar.profile_name_fault(name):
        raise Refusal(f"that cannot be the profile's name: {fault}. Pick one: {hint}")
    return name


def _yes(args: list[str], yes: bool) -> list[str]:
    return args + ["-y"] if yes else args


def hire(desk: Desk, io: Io, id: str, name: str = "", alias: bool = False, yes: bool = False) -> int:
    """Installs the employee as a new profile. 0 when it is installed, 1 when the person said no."""
    _, short = grammar.split_id(id)
    name = _profile_name(name or short, f"hermes harnsy-hr hire {id} --name <name>")
    state = desk.state
    profile, folder = state.profile_dir(name), state.distribution_dir(name)
    if profile.exists():
        hint = f"`hermes harnsy-hr update {name}` brings it up to date; " if name in state.hires() else ""
        raise Refusal(f"a Hermes profile named {name} is already there ({profile}) and is not replaced. {hint}"
                      f"to hire under another name: hermes harnsy-hr hire {id} --name <name>")
    offer = desk.offer(id)
    io.say(preview.details(offer))
    io.say(f"\nIt becomes the Hermes profile «{name}», beside your own:\n  its files are built in  {folder}\n"
           f"    (they stay there: `hermes profile update` reads them again)\n  Hermes installs them to {profile}\n"
           "Your own profile and its SOUL.md are not touched.\n")
    if not yes and not io.ask(f"Install {preview.plain(offer.entry.title)} as the profile «{name}»? [y/N] "):
        io.say("Nothing was installed.")
        return 1
    folders.remove(folder)  # a leftover of a run that did not finish
    folders.write_tree(folder, offer.tree)
    io.say("\nHermes Agent takes over: it shows what it installs" + ("." if yes else " and asks you once more."))
    code = io.run(_yes(["profile", "install", str(folder), "--name", name] + (["--alias"] if alias else []), yes))
    if not folders.holds(profile, offer.tree):
        folders.remove(folder)
        left = f" Hermes left {profile}: `hermes profile delete {name}` removes it." if profile.exists() else ""
        io.say(f"\n{id} was not installed: Hermes did not make the profile (cancelled, or see its message above; "
               f"exit code {code}). What this plugin built was removed.{left}")
        return 1
    state.record(name, id, offer.entry.version)
    io.say(f"\nHired: {preview.plain(offer.entry.title)} {offer.entry.version} is the profile «{name}».\nNext:\n"
           f"  hermes -p {name} setup    pick its model once (a new profile has no model settings)\n"
           f"  hermes -p {name} chat     talk to it")
    return 0


def _hired(state: State, name: str) -> dict:
    """The record of a hire; refuses a name this plugin did not hire, and a profile that is not the one it installed."""
    hired = state.hires().get(name) if not grammar.profile_name_fault(name) else None
    if not hired or not grammar.is_id(str(hired.get("id", ""))):
        raise Refusal("no employee was hired under that profile name. See: hermes harnsy-hr list")
    profile, folder = state.profile_dir(name), state.distribution_dir(name)
    if profile.exists() and not folders.installed_from(profile, folder):
        raise Refusal(f"the profile {name} is not the one this plugin installed (its distribution.yaml names another "
                      "source), so it is left alone")
    return hired


def _changes(old: dict[str, bytes], offer: Offer) -> str:
    new = folders.relative_files(offer.tree)
    lines = [f"  {'new    ' if p not in old else 'changed'}  {p}" for p in new if old.get(p) != new[p]]
    lines += [f"  gone     {p}" for p in old if p not in new]
    return "\n".join(lines) or "  (no file differs)"


def update(desk: Desk, io: Io, name: str, yes: bool = False) -> int:
    """Brings a hired employee to the catalog's current version. Config, memory and .env stay the person's."""
    state = desk.state
    hired = _hired(state, name)
    profile, folder = state.profile_dir(name), state.distribution_dir(name)
    if not profile.is_dir():
        raise Refusal(f"the profile {name} is gone. `hermes harnsy-hr fire {name}` tidies up what is left of it")
    offer = desk.offer(hired["id"])
    old = folders.read_folder(folder)
    if old == folders.relative_files(offer.tree) and folders.holds(profile, offer.tree):
        io.say(f"«{name}» is up to date: {preview.plain(offer.entry.title)} {offer.entry.version}.")
        return 0
    io.say(f"Update «{name}»: {preview.plain(offer.entry.title)} {hired.get('version', '?')} → {offer.entry.version}\n"
           f"{_changes(old, offer)}\n\nNotice:\n\n{preview.plain(offer.tree.notice)}\n"
           "Your settings, memory and .env in the profile stay as they are.\n")
    if not yes and not io.ask(f"Update the profile «{name}»? [y/N] "):
        io.say("Nothing was changed.")
        return 1
    fresh, kept = folder.with_name(name + ".new"), folder.with_name(name + ".old")  # a profile name holds no dot
    folders.remove(fresh), folders.remove(kept)
    folders.write_tree(fresh, offer.tree)
    if folder.exists():
        folder.rename(kept)
    fresh.rename(folder)
    io.say("Hermes Agent takes over" + ("." if yes else ": it asks you once more."))
    code = io.run(_yes(["profile", "update", name], yes))
    if not folders.holds(profile, offer.tree):
        folders.remove(folder)
        if kept.exists():
            kept.rename(folder)
        io.say(f"\n«{name}» was not updated (cancelled, or see Hermes' message above; exit code {code}). "
               "The version it had is still in place.")
        return 1
    folders.remove(kept)
    state.record(name, hired["id"], offer.entry.version)
    io.say(f"\nUpdated: «{name}» is {preview.plain(offer.entry.title)} {offer.entry.version}.")
    return 0


def fire(state: State, io: Io, name: str, yes: bool = False) -> int:
    """Deletes a hired employee's profile through Hermes, then the folder this plugin built for it."""
    _hired(state, name)
    profile, folder = state.profile_dir(name), state.distribution_dir(name)
    if profile.exists():
        io.say(f"Hermes Agent deletes the profile «{name}»" + ("." if yes else ": it asks you to confirm."))
        code = io.run(_yes(["profile", "delete", name], yes))
        if profile.exists():
            io.say(f"\n«{name}» was not deleted (cancelled, or see Hermes' message above; exit code {code}).")
            return 1
    folders.remove(folder)
    state.forget(name)
    io.say(f"\nFired: the profile «{name}» and the files this plugin kept for it are gone.")
    return 0
