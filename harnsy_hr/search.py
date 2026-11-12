"""Search of the catalog's cards by the words a person types: a role, a skill, a need. The same rules as the
catalog's own MCP server: more words matched first, then the better match, then the one named by the very word."""

from __future__ import annotations

import re

from .errors import Refusal
from .types import Entry

MAX_QUERY_BYTES = 256
MAX_QUERY_TERMS = 16  # different words that are searched for

# Words too common in a request to tell one employee from another.
_STOP = frozenset("a an the and or for to of on in with who that can me my i we our need find want someone somebody "
                  "employee agent hire install hr".split())
_ENDINGS = ("ments", "ment", "ings", "ing", "ants", "ant", "ers", "er", "ed", "es", "s")
# A field's weight: where a word is found says how much the employee is about it.
_NAME, _SKILL, _SUMMARY, _OTHER = 5, 3, 2, 1


def _tokens(text: str) -> list[str]:
    """Lowercase words of letters and digits."""
    return re.findall(r"[^\W_]+", text.lower())


def _cut(word: str, ending: str) -> str | None:
    cut = word.removesuffix(ending)
    return cut if cut != word and len(cut.encode()) >= 4 else None


def _singular(word: str) -> str:
    """Drops a plural s, so that «accountants» names the «accountant»."""
    return _cut(word, "s") or word


def _stem(word: str) -> str:
    """Cuts a common English ending, so that «accountant» finds «accounting». A rough cut for matching, not grammar:
    a word keeps at least four letters."""
    for ending in _ENDINGS:
        if cut := _cut(word, ending):
            return cut
    return word


def _index(e: Entry) -> tuple[dict[str, int], set[str]]:
    """An employee's searchable words: stems with the weight of the best field each stands in, and the words of its
    title and id as written, in the singular."""
    weights: dict[str, int] = {}
    name = e.id.partition("/")[2]
    fields = [(_NAME, [e.title, name]), (_SKILL, [*e.skills, *e.tags, *e.keywords]), (_SUMMARY, [e.summary]),
              (_OTHER, [e.department, e.persona_name, *e.industries])]
    for weight, texts in fields:
        for word in _tokens(" ".join(texts)):
            stem = _stem(word)
            weights[stem] = max(weights.get(stem, 0), weight)
    return weights, {_singular(w) for w in _tokens(e.title + " " + name)}


def _score(weights: dict[str, int], word: str) -> int:
    """How well an employee answers one word: the best weight among the words it matches."""
    best = weights.get(word, 0)
    if len(word.encode()) < 4:
        return best  # a short word («go», «ui») matches only itself
    for known, weight in weights.items():
        if weight > best and len(known.encode()) >= 4 and (known.startswith(word) or word.startswith(known)):
            best = weight
    return best


def _terms(text: str) -> list[tuple[str, str]]:
    """A request's words, each once, without the ones that tell nothing: (as written in the singular, its stem)."""
    if len(text.encode()) > MAX_QUERY_BYTES:
        raise Refusal(f"the search is longer than {MAX_QUERY_BYTES} bytes; say it in a few words")
    terms = list(dict.fromkeys((_singular(w), _stem(w)) for w in _tokens(text) if _stem(w) not in _STOP))
    if len(terms) > MAX_QUERY_TERMS:
        raise Refusal(f"the search has more than {MAX_QUERY_TERMS} different words; say it in a few words")
    return terms


def search(entries: list[Entry], text: str = "", department: str = "") -> list[Entry]:
    """The employees in the department, when one is given, that match at least one word of the text; no words lists
    everyone in the feed's order."""
    terms = _terms(text)
    hits = []
    for e in entries:
        if department and department.casefold() != e.department.casefold():
            continue
        weights, named = _index(e)
        scores = [s for _, stem in terms if (s := _score(weights, stem)) > 0]
        if scores or not terms:
            hits.append((-len(scores), -sum(scores), -sum(word in named for word, _ in terms), len(hits), e))
    return [hit[-1] for hit in sorted(hits, key=lambda hit: hit[:-1])]
