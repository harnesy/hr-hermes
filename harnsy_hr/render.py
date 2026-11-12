"""Turns a verified employee into a profile distribution for Hermes Agent: distribution.yaml, one SOUL.md, its skills
byte for byte under skills/<publisher>/, its casebook as a skill, and the notice with its licence and credits.

There is no config.yaml: the model settings of the profile are the person's. The files are the same, byte for byte,
as the catalog's own MCP server renders for Hermes Agent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import persona
from .bundle import clean_relative
from .errors import Refusal
from .grammar import CASEBOOK, split_id
from .notice import OWN_AUTHOR, SPACE, is_own, notice, publisher_name, title
from .persona import CASEBOOK_SKILL
from .types import Employee

CHANGE = "rendered for hermes"  # the «Changes:» of the notice


@dataclass
class Tree:
    """An employee rendered for Hermes Agent. Paths start with the employee's name and use forward slashes."""

    name: str  # the employee's short name: its id without the publisher
    soul: bytes  # SOUL.md: who the employee is and its job; it ends with the credit line
    notice: str  # the notice's text: licence, source, changes, credits
    files: list[tuple[str, bytes]]  # in path order


def one_line(s: str) -> str:
    """The words of s with single spaces between them."""
    for space in SPACE:
        s = s.replace(space, " ")
    return " ".join(part for part in s.split(" ") if part)


def yaml_string(s: str) -> str:
    """s as a double-quoted YAML scalar on one line (a JSON string is one)."""
    return json.dumps(s, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _distribution(e: Employee, name: str) -> str:
    """distribution.yaml. Every value is a quoted string: Hermes reads YAML 1.1, where a bare `no` or `1.0` is not a
    string."""
    description = title(e)
    if summary := one_line(e.entry.summary):
        description += ": " + summary
    author = OWN_AUTHOR if is_own(e) else publisher_name(e)
    out = (f"name: {yaml_string(name)}\nversion: {yaml_string(e.entry.version)}\n"
           f"description: {yaml_string(description)}\nauthor: {yaml_string(author)}\n")
    if e.doc.license:
        out += f"license: {yaml_string(e.doc.license)}\n"
    return out


def _casebook_wrapper(e: Employee) -> str:
    """The SKILL.md that makes the casebook a skill: the cases themselves are its reference, unchanged."""
    whose = "the " + e.doc.role_name
    if e.doc.persona_name:
        whose = e.doc.persona_name + ", the " + e.doc.role_name
    description = (f"Worked cases of {one_line(whose)}: situation, decision, why. Read it when a case like these comes "
                   "up, before a decision your principles do not settle.")
    return (f"---\nname: {CASEBOOK_SKILL}\ndescription: {yaml_string(description)}\n---\n\n# Casebook\n\n"
            "The worked cases are in `references/persona-casebook.md` in this skill's folder. Read that file when a "
            "case like these comes up. Quote only from it and never invent a quote.\n")


def render(e: Employee) -> Tree:
    """The employee's profile distribution, in a folder named after it."""
    publisher, name = split_id(e.entry.id)
    home = name + "/"
    skills = home + "skills/" + publisher + "/"
    soul = ("# " + title(e) + "\n\n" + persona.intro(e) + persona.who(e) + persona.job(e)
            + persona.credit_line(e, CHANGE)).encode()
    text = notice(e, CHANGE)
    files = [(home + "SOUL.md", soul), (home + "distribution.yaml", _distribution(e, name).encode()),
             (home + "NOTICE.md", ("# Notice\n\n" + text).encode())]
    if persona.has_casebook(e):
        files.append((skills + CASEBOOK_SKILL + "/SKILL.md", _casebook_wrapper(e).encode()))
        files.append((skills + CASEBOOK_SKILL + "/references/persona-casebook.md", e.files[CASEBOOK]))
    files += [(skills + path.removeprefix("skills/"), content) for path, content in e.files.items() if path.startswith("skills/")]
    files.sort()
    _check_paths(home, files)
    return Tree(name=name, soul=soul, notice=text, files=files)


def _check_paths(home: str, files: list[tuple[str, bytes]]) -> None:
    """A second gate, independent of the checks on the bundle: every path is a clean relative one inside the
    employee's folder, and none is there twice."""
    paths = [p for p, _ in files]
    if len(set(paths)) != len(paths) or not all(p.startswith(home) and clean_relative(p) for p in paths):
        raise Refusal("the employee's files do not make a clean folder (a path twice, or one that leaves the folder)")
