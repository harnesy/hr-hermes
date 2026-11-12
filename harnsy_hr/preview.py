"""What a person reads before they say yes: the employee's card, what it needs, its files, its notice."""

from __future__ import annotations

import re
import unicodedata

from . import persona
from .desk import Offer
from .folders import relative_files
from .notice import publisher_name, title
from .types import Entry

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029]")


def plain(text: str) -> str:
    """Text from the catalog, safe to print: without control characters (a terminal would obey them) and without the
    characters nobody sees (Unicode category Cf: they turn text around or hide a part of it, so a person would read
    something other than what is written to the files). Only what is printed goes through here, never a file."""
    return "".join(c for c in _CONTROL.sub("", text) if unicodedata.category(c) != "Cf")


def one_line(text: str) -> str:
    """A name read from the disk, printed on a line of its own: as `plain`, and a line break in it is a space."""
    return plain(text).replace("\n", " ").replace("\t", " ")


def card(e: Entry) -> str:
    """An employee as a search shows it."""
    lines = [f"{e.id}  {plain(e.title)} {e.version}" + (f"  ({plain(e.persona_name)})" if e.persona_name else "")]
    if e.summary:
        lines.append("    " + plain(e.summary))
    facts = [f for f in (plain(e.department), "licence " + plain(e.license) if e.license else "") if f]
    if facts:
        lines.append("    " + ", ".join(facts))
    return "\n".join(lines)


def _size(n: int) -> str:
    return f"{n} bytes" if n < 1024 else f"{n / 1024:.1f} KB"


def details(offer: Offer) -> str:
    """The card in full, what the employee needs, every file with its size, and the whole notice."""
    e, entry = offer.employee, offer.entry
    files = relative_files(offer.tree)
    needs = plain(persona.needs(e)) or "- Nothing but a model.\n"
    scripts = sum("/scripts/" in path for path in files)
    out = [f"{plain(title(e))} {entry.version}  ({entry.id})"]
    if e.doc.persona_name:
        out.append(f"  Name: {plain(e.doc.persona_name)}, an AI agent")
    if entry.summary:
        out.append("  " + plain(entry.summary))
    out.append(f"  Publisher: {plain(publisher_name(e))}    Licence: {plain(e.doc.license) or 'none stated'}")
    out.append(f"  Page: {plain(entry.cv_url) or 'https://hr.harnsy.dev/e/' + entry.id}")
    out.append("\nWhat it needs:\n" + needs.rstrip("\n"))
    out.append(f"\nFiles ({len(files)}, {_size(sum(map(len, files.values())))}):")
    out += [f"  {path}  ({_size(len(content))})" for path, content in files.items()]
    if scripts:
        out.append(f"  {scripts} of them are scripts of its skills. This plugin saves them as files and never runs "
                   "them; the employee may run them later, with Hermes' own approvals.")
    out.append("\nNotice (it is saved with the employee as NOTICE.md; keep it there):\n")
    out.append(plain(offer.tree.notice).rstrip("\n"))
    return "\n".join(out)
