"""The plugin's own folder under the Hermes home: what it remembers and the distribution folders it builds.

    <Hermes home>/harnsy-hr/state.json           the highest feed number seen per catalog key, and the hires
    <Hermes home>/harnsy-hr/profiles/<name>/     the profile distribution of a hired employee

A distribution folder stays on the disk: `hermes profile update` reads it again from the place Hermes recorded.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import Refusal

FOLDER = "harnsy-hr"


def hermes_root(environ=os.environ) -> Path:
    """The root Hermes home: the one that holds profiles/, also when a profile is the active home."""
    try:
        from hermes_constants import get_default_hermes_root  # Hermes Agent's public plugin API
        return Path(get_default_hermes_root())
    except ImportError:  # outside Hermes (tests, a bare interpreter): the same rule by hand
        native = Path.home() / ".hermes"
        given = environ.get("HERMES_HOME", "").strip()
        if not given:
            return native
        home = Path(os.path.expanduser(given))
        if home.resolve().is_relative_to(native.resolve()):
            return native
        return home.parent.parent if home.parent.name == "profiles" else home


class State:
    """The plugin's folder under one Hermes root."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.folder = self.root / FOLDER
        self._file = self.folder / "state.json"

    def profile_dir(self, name: str) -> Path:
        """Where Hermes keeps the profile of that name."""
        return self.root / "profiles" / name

    def distribution_dir(self, name: str) -> Path:
        """Where this plugin builds the distribution folder of the profile of that name."""
        return self.folder / "profiles" / name

    def _read(self) -> dict:
        try:
            raw = self._file.read_bytes()
        except FileNotFoundError:
            return {}
        except OSError as err:
            raise Refusal(f"{self._file}: cannot be read ({type(err).__name__})") from None
        try:
            doc = json.loads(raw)
            ok = isinstance(doc, dict) and all(isinstance(doc.get(k, {}), dict) for k in ("seq", "hires"))
        except ValueError:
            ok = False
        if not ok:
            raise Refusal(f"{self._file} is damaged. It holds the newest catalog feed number this machine has seen; "
                          "remove the file to start over")
        return doc

    def _write(self, doc: dict) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self._file)

    def check_seq(self, kid: str, seq: int) -> None:
        """Refuses a feed older than one already seen under the same key (a replayed old feed could bring back a
        version revoked since), and remembers the highest."""
        doc = self._read()
        seen = doc.get("seq", {}).get(kid)
        if isinstance(seen, int) and seq < seen:
            raise Refusal(f"the catalog's feed is older than one this machine has already seen (number {seq}, seen "
                          f"{seen}): refused. If the catalog was rolled back on purpose, remove {self._file}")
        if seen != seq:
            doc.setdefault("seq", {})[kid] = seq
            self._write(doc)

    def hires(self) -> dict[str, dict]:
        """The hired employees by profile name: {"id", "version"}."""
        return {name: h for name, h in self._read().get("hires", {}).items() if isinstance(h, dict)}

    def record(self, name: str, id: str, version: str) -> None:
        doc = self._read()
        doc.setdefault("hires", {})[name] = {"id": id, "version": version}
        self._write(doc)

    def forget(self, name: str) -> None:
        doc = self._read()
        if doc.get("hires", {}).pop(name, None) is not None:
            self._write(doc)
