"""The front desk: fetches the catalog, checks all of it, and offers an employee ready to install."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from . import catalog, grammar, hermesscan, render
from .errors import Refusal
from .keys import Setup
from .state import State
from .types import Employee, Entry, Feed


@dataclass
class Offer:
    """A verified employee and its profile distribution, checked against Hermes' scanner."""

    employee: Employee
    tree: render.Tree

    @property
    def entry(self) -> Entry:
        return self.employee.entry

    def paths(self) -> list[str]:
        """The files of the distribution, from its folder."""
        return [p.removeprefix(self.tree.name + "/") for p, _ in self.tree.files]


class Desk:
    def __init__(self, setup: Setup, state: State, source, now: datetime | None = None) -> None:
        self.setup, self.state, self.source = setup, state, source
        self.now = now or datetime.now(timezone.utc)
        self._feed: Feed | None = None

    def feed(self) -> Feed:
        """The catalog's feed, verified, and not older than one this machine has seen."""
        if self._feed is None:
            feed = catalog.fetch_feed(self.source, self.setup.need_keys(), catalog.HOST, self.now)
            self.state.check_seq(feed.kid, feed.seq)
            self._feed = feed
        return self._feed

    def entry(self, id: str) -> Entry:
        grammar.split_id(id)
        entry = self.feed().entry(id)
        if entry is None:
            raise Refusal(f"the catalog has no employee {id} (or its version was withdrawn). "
                          "Search: hermes harnsy-hr search <words>")
        return entry

    def offer(self, id: str) -> Offer:
        """Downloads the employee, verifies it, renders it, and refuses it when Hermes would leave its SOUL.md out."""
        entry = self.entry(id)
        employee = catalog.fetch_employee(self.source, self.setup.need_keys(), catalog.HOST, self.feed(), entry)
        tree = render.render(employee)
        if hits := hermesscan.scan(tree.soul.decode()):
            raise Refusal(f"{id} cannot work in Hermes Agent as it is written: Hermes' own scanner for profile files "
                          f"would leave its SOUL.md out (pattern: {', '.join(hits)}), and the profile would run "
                          "without its role. Nothing was installed. The catalog's authors have to reword it")
        return Offer(employee, tree)
