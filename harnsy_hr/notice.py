"""The notice that travels with an installed employee: who made it, its licence, where it is, what was changed, the
works it is built on. The wording is fixed: it says what CC BY 4.0 asks for."""

from __future__ import annotations

from .types import Employee

# The catalog's own publisher and how its works are credited.
OWN_PUBLISHER = "harnsy"
OWN_AUTHOR = "harnsy (Pavel Buchnev)"
OWN_HOLDER = "Pavel Buchnev (harnsy)"

CC0 = "CC0-1.0"  # the public-domain dedication: a work under it carries no copyright notice

# Text licences the catalog takes, as a notice names them.
_LICENCE_LINES = {
    "CC-BY-4.0": "Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).",
    CC0: "Dedicated to the public domain under CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/).",
}

# What the reference renderer reads as white space (Unicode White_Space).
SPACE = "\t\n\v\f\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"


def title(e: Employee) -> str:
    """The employee's display title."""
    return e.entry.title or e.doc.role_name


def is_own(e: Employee) -> bool:
    """Whether the employee is the catalog's own: its text is harnsy's, not another publisher's."""
    return e.entry.publisher == OWN_PUBLISHER


def publisher_name(e: Employee) -> str:
    return e.entry.publisher_name or e.entry.publisher


def _source_url(e: Employee) -> str:
    """The employee's page on the catalog."""
    return e.entry.cv_url or "https://hr.harnsy.dev/e/" + e.entry.id


def _year(e: Employee) -> str:
    """The year the employee was first published: the feed's date, else the day its file was packed."""
    for date in (e.entry.published, e.manifest.created_at):
        raw = date.encode()
        if len(raw) >= 4:
            return raw[:4].decode("utf-8", "replace")
    return ""


def _text_licence(expr: str) -> tuple[str, bool]:
    """The line for the employee's text, and whether that text is dedicated to the public domain. Other ids of the
    bundle's licence expression are the licences of parts of its skills."""
    for id in expr.split(" AND "):
        id = id.strip(SPACE)
        if id in _LICENCE_LINES:
            return _LICENCE_LINES[id], id == CC0
    if not expr:
        return "No licence is stated for this employee: do not copy or redistribute it.", False
    return "Licensed under " + expr + ".", False


def _author(e: Employee, dedicated: bool) -> str:
    """Who made the work, with the copyright notice of its first publication. A work dedicated to the public domain
    has no copyright notice: its author is named as a courtesy."""
    name = holder = publisher_name(e)
    where = ", published on hr.harnsy.dev."
    if is_own(e):
        name, holder, where = OWN_AUTHOR, OWN_HOLDER, "."
    if dedicated:
        return name + "."
    if year := _year(e):
        holder = year + " " + holder
    return name + ", © " + holder + where


def credit(e: Employee, change: str) -> str:
    """The head of the notice in one line. It is also the last line of the persona file, so the credit survives when
    only that file is copied."""
    licence, dedicated = _text_licence(e.doc.license)
    return (f"{title(e)} {e.entry.version} by {_author(e, dedicated)} {licence} Source: {_source_url(e)}. "
            f"Changes: {change}. Provided as is, without warranty of any kind (see the licence).")


def _has_skill_licence(e: Employee) -> bool:
    """Whether a skill of the employee carries its own LICENSE file."""
    return any(p.startswith("skills/") and p.removeprefix("skills/").partition("/")[2] == "LICENSE" for p in e.files)


def notice(e: Employee, change: str) -> str:
    """The credit line, who stands behind the work, the publisher's note, the licence of parts of its skills, the
    works it is built on as the bundle lists them, and what the licence does not cover."""
    out = [credit(e, change) + "\n"]
    by, names = "the publisher", "The names and logos «harnsy» and «hr.harnsy.dev» are not covered by this licence."
    if is_own(e):
        by = OWN_PUBLISHER
        names = ("The names and logos «harnsy» and «hr.harnsy.dev», and the picture of this employee (not included "
                 "here), are not covered by this licence.")
    else:
        out.append("\nhr.harnsy.dev lists this work; it is not made or endorsed by harnsy.\n")
    if e.entry.license_note:
        out.append(f"\nNote from {by}: {e.entry.license_note}\n")
    if _has_skill_licence(e):
        out.append("\nSome skills carry another licence for the parts adapted from other works or for their scripts "
                   "(for example MIT): it is the `LICENSE` file in that skill's folder, and it applies to those parts")
        if e.doc.license:
            out.append(" (the bundle's licence: " + e.doc.license + ")")
        out.append(".\n")
    if e.doc.attribution:
        out.append("\nBuilt on:\n")
        for a in e.doc.attribution:
            out.append(f"- {a.name}, {a.url}, {a.license}, {'modified' if a.modified else 'not modified'}\n")
    out.append("\n" + names + "\n")
    return "".join(out)
