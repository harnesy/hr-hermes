"""The shapes of bundle v1: the feed's card of an employee, a bundle's manifest, the employee itself."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from . import jsonread as j


def _typed(doc: dict, what: str, *keys: str) -> None:
    """Fields this plugin does not use are still read for their type: a file with a field of the wrong type is
    refused whole, as the catalog's own reader does."""
    for key in keys:
        j.text(doc, key, what)


@dataclass(frozen=True)
class Attribution:
    """One public credit of a bundle."""

    name: str
    url: str
    license: str
    modified: bool

    @staticmethod
    def read(doc: dict, what: str) -> "Attribution":
        return Attribution(j.text(doc, "name", what), j.text(doc, "url", what), j.text(doc, "license", what),
                           j.flag(doc, "modified", what))


@dataclass
class Entry:
    """One bundle of the feed: its card and where its file is."""

    id: str
    kind: str
    version: str
    title: str
    summary: str
    persona_name: str
    department: str
    industries: list[str]
    tags: list[str]
    skills: list[str]
    keywords: list[str]
    published: str
    publisher: str
    publisher_name: str
    url: str
    sha256: str
    size: int
    avatar_url: str
    cv_url: str
    license: str
    license_note: str
    attribution: list[Attribution]

    @staticmethod
    def read(doc: dict) -> "Entry":
        w = "feed.json"
        _typed(doc, w, "updated", "subtitle")
        return Entry(
            id=j.text(doc, "id", w), kind=j.text(doc, "kind", w), version=j.text(doc, "version", w),
            title=j.text(doc, "title", w), summary=j.text(doc, "summary", w),
            persona_name=j.text(j.obj(doc, "persona", w), "name", w), department=j.text(doc, "department", w),
            industries=j.texts(doc, "industries", w), tags=j.texts(doc, "tags", w), skills=j.texts(doc, "skills", w),
            keywords=j.texts(doc, "keywords", w), published=j.text(doc, "published", w),
            publisher=j.text(doc, "publisher", w), publisher_name=j.text(doc, "publisher_name", w),
            url=j.text(doc, "url", w), sha256=j.text(doc, "sha256", w), size=j.integer(doc, "size", w),
            avatar_url=j.text(doc, "avatar_url", w), cv_url=j.text(doc, "cv_url", w), license=j.text(doc, "license", w),
            license_note=j.text(doc, "license_note", w),
            attribution=[Attribution.read(a, w) for a in j.objects(doc, "attribution", w)])


@dataclass
class Feed:
    """A verified v1/feed.json: the employees it serves, in its order."""

    kid: str  # the key that signed it
    seq: int
    expires: datetime
    entries: list[Entry]  # employees only, without the revoked versions

    def entry(self, id: str) -> Entry | None:
        found = None
        for e in self.entries:
            if e.id == id:
                found = e
        return found


@dataclass
class Manifest:
    """A bundle's manifest.json: what the file is and the SHA-256 of every other file but signatures/*."""

    format: str
    format_version: int
    id: str
    version: str
    kind: str
    created_at: str
    files: dict[str, str]

    @staticmethod
    def read(raw: bytes) -> "Manifest":
        w = "manifest.json"
        doc = j.parse(raw, w)
        files = j.obj(doc, "files", w)
        _typed(doc, w, "publisher", "cv_url")
        return Manifest(j.text(doc, "format", w), j.integer(doc, "format_version", w), j.text(doc, "id", w),
                        j.text(doc, "version", w), j.text(doc, "kind", w), j.text(doc, "created_at", w),
                        {name: j.text(files, name, w) for name in files})


@dataclass
class Competency:
    """One thing the employee knows and how it works with it."""

    name: str
    summary: str
    knows: str
    works: str
    hands_over: str


@dataclass
class Doc:
    """bundle.json: the employee. A bundle's harnsy Max list is not read: it means nothing outside harnsy."""

    persona_name: str = ""
    character: str = ""
    principles: list[str] = field(default_factory=list)
    voice_rules: list[str] = field(default_factory=list)
    voice_samples: list[str] = field(default_factory=list)
    role_name: str = ""
    mandate: str = ""
    deliverable: str = ""
    prompt: str = ""
    tools: list[tuple[str, str]] = field(default_factory=list)  # (name, lowest version)
    keys: list[str] = field(default_factory=list)  # names only: a key itself is never in a bundle
    competencies: list[Competency] = field(default_factory=list)
    license: str = ""
    attribution: list[Attribution] = field(default_factory=list)
    skills: list[tuple[str, str]] = field(default_factory=list)  # (name, description)

    @staticmethod
    def read(raw: bytes) -> "Doc":
        w = "bundle.json"
        doc = j.parse(raw, w)
        persona, role, requires = j.obj(doc, "persona", w), j.obj(doc, "role", w), j.obj(doc, "requires", w)
        voice = j.obj(persona, "voice", w)
        _typed(doc, w, "schema")
        _typed(role, w, "department", "tagline")
        j.texts(role, "industries", w), j.texts(role, "keywords", w)
        for c in j.objects(doc, "competencies", w):
            _typed(c, w, "key")
        return Doc(
            persona_name=j.text(persona, "name", w), character=j.text(persona, "character", w),
            principles=[j.text(p, "text", w) for p in j.objects(persona, "principles", w)],
            voice_rules=j.texts(voice, "rules", w),
            voice_samples=[j.text(s, "text", w) for s in j.objects(voice, "samples", w)],
            role_name=j.text(role, "name", w), mandate=j.text(role, "mandate", w),
            deliverable=j.text(role, "deliverable", w), prompt=j.text(role, "prompt", w),
            tools=[(j.text(t, "name", w), j.text(t, "min", w)) for t in j.objects(requires, "tools", w)],
            keys=j.texts(requires, "keys", w),
            competencies=[Competency(j.text(c, "name", w), j.text(c, "summary", w), j.text(c, "knows", w),
                                     j.text(c, "works", w), j.text(c, "hands_over", w))
                          for c in j.objects(doc, "competencies", w)],
            license=j.text(doc, "license", w),
            attribution=[Attribution.read(a, w) for a in j.objects(doc, "attribution", w)],
            skills=_skill_refs(j.items(doc, "skills", w)))


def _skill_refs(raw: list) -> list[tuple[str, str]]:
    """The skills a bundle carries in skills/<name>/. An older bundle may hold plain strings there: labels that carry
    nothing, left out."""
    refs = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"] \
                and isinstance(item.get("description", ""), (str, type(None))):
            refs.append((j.text(item, "name", "bundle.json"), j.text(item, "description", "bundle.json")))
    return refs


@dataclass
class Employee:
    """One verified bundle."""

    entry: Entry
    manifest: Manifest
    manifest_sha256: str
    doc: Doc
    files: dict[str, bytes]  # every file the manifest lists, by its path in the bundle
