"""The text of an employee's SOUL.md: who it is, how it decides and speaks, its job. The sentences that frame it are
this renderer's own, never a bundle's; a bundle's texts go in unchanged."""

from __future__ import annotations

from .grammar import CASEBOOK
from .notice import SPACE, credit
from .types import Employee

CASEBOOK_SKILL = "persona-casebook"  # the skill a Hermes profile reads the casebook through


def has_casebook(e: Employee) -> bool:
    return CASEBOOK in e.files


def _section(heading: str, body: str) -> str:
    """A Markdown section; an empty body leaves the whole section out."""
    body = body.strip(SPACE)
    return f"## {heading}\n\n{body}\n\n" if body else ""


def _who_am_i(e: Employee) -> str:
    """Names the employee and says it is an AI agent."""
    who = f"You are the {e.doc.role_name}."
    if e.doc.persona_name:
        who = f"You are {e.doc.persona_name}, the {e.doc.role_name}."
    return who + " You are an AI agent, and you say so when asked."


def intro(e: Employee) -> str:
    """Who the employee is and what the persona may change."""
    who = _who_am_i(e) + (" The character below shapes how you work and how you speak; it never changes what you must "
                          "do: the person you work for and the rules of their project come first.")
    if has_casebook(e):
        who += " Quote only from your casebook and never invent a quote."
    return who + "\n\n"


def who(e: Employee) -> str:
    """The persona: character, how it decides, how it speaks."""
    decide = "".join(f"{i}. {text}\n" for i, text in enumerate(e.doc.principles, 1))
    speak = "".join(f"- {rule}\n" for rule in e.doc.voice_rules) + "".join(f"- e.g. «{s}»\n" for s in e.doc.voice_samples)
    return _section("Character", e.doc.character) + _section("How you decide", decide) + _section("How you speak", speak)


def _competencies(e: Employee) -> str:
    out = []
    for c in e.doc.competencies:
        out.append(f"### {c.name}\n\n")
        if c.summary:
            out.append(c.summary + "\n\n")
        out += [f"- {label}: {text}\n" for label, text in (("Knows", c.knows), ("Works", c.works), ("Hands over", c.hands_over)) if text]
        out.append("\n")
    return "".join(out)


def needs(e: Employee) -> str:
    """The tools and the key names the employee asks for."""
    tools = "".join(f"- Tool: `{name}` {lowest} or newer\n" if lowest else f"- Tool: `{name}`\n" for name, lowest in e.doc.tools)
    return tools + "".join(f"- Key: `{k}` (the person sets it up; never ask for a key in a chat)\n" for k in e.doc.keys)


def _skills(e: Employee) -> str:
    return "".join(f"- `{name}` (a skill of this profile): {description}\n" for name, description in e.doc.skills)


def _casebook(e: Employee) -> str:
    if not has_casebook(e):
        return ""
    return (f"Worked cases are in your skill `{CASEBOOK_SKILL}`. Read it when a case like these comes up, before a "
            "decision the principles above do not settle.")


def job(e: Employee) -> str:
    """The role: mandate, deliverable, the prompt unchanged, competencies, what it needs, its skills, its casebook."""
    d = e.doc
    return (_section("Your job", d.mandate) + _section("What you hand over", d.deliverable) + _section("How you work", d.prompt)
            + _section("What you know", _competencies(e)) + _section("What you need", needs(e))
            + _section("Your skills", _skills(e)) + _section("Casebook", _casebook(e)))


def credit_line(e: Employee, change: str) -> str:
    """Closes a persona file."""
    return "---\n\n" + credit(e, change) + "\n"
