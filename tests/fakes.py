"""Stand-ins for Hermes Agent and for the person at the terminal."""

from __future__ import annotations

import argparse
import base64
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harnsy_hr import cli, commands, keys, slash
from harnsy_hr.desk import Desk
from harnsy_hr.hiring import Io
from harnsy_hr.sources import DirSource
from harnsy_hr.state import State
from tests.kit import Kit, sample


class FakeHermes:
    """Does what `hermes profile install|update|delete` does to the folders, or declines like a person who says no.
    A declined or failed run ends with code 0, as the real one does."""

    def __init__(self, root: Path) -> None:
        self.root, self.calls, self.decline, self.before = Path(root), [], False, None

    def __call__(self, args: list[str]) -> int:
        self.calls.append(args)
        if self.before:
            self.before()
        if self.decline:
            return 0
        verb, name = args[1], args[args.index("--name") + 1] if "--name" in args else args[2]
        profile = self.root / "profiles" / name
        if verb == "delete":
            shutil.rmtree(profile)
            return 0
        source = Path(args[2]) if verb == "install" else Path((profile / "distribution.yaml").read_text().split("source: ")[1].strip())
        if verb == "install" and profile.exists():
            return 1
        shutil.copytree(source, profile, dirs_exist_ok=True)
        (profile / "memories").mkdir(exist_ok=True)
        with open(profile / "distribution.yaml", "a") as f:
            f.write(f"source: {source}\n")
        return 0


class HiringCase(unittest.TestCase):
    """A catalog release, a Hermes home, a stand-in Hermes and a person who answers as told."""

    def setUp(self) -> None:
        self.k = Kit()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.release, self.home = Path(tmp.name) / "release", Path(tmp.name) / "home"
        self.state = State(self.home)
        self.hermes = FakeHermes(self.home)
        self.said: list[str] = []
        self.asked: list[str] = []
        self.answer = True
        self.io = Io(run=self.hermes, ask=self._ask, say=self.said.append)
        self.publish("1.0.0")

    def _ask(self, question: str) -> bool:
        self.asked.append(question)
        return self.answer

    def publish(self, version: str, seq: int = 7, **files) -> None:
        packs = [self.k.pack("harnsy/reviewer", version, sample("reviewer") | files),
                 self.k.pack("harnsy/test", "1.0.0", sample("test"))]
        self.k.release(self.release, packs, lambda f: f.update(seq=seq))

    def desk(self) -> Desk:
        return Desk(keys.Setup(base="", keys=self.k.keys, test=False), self.state, DirSource(self.release), self.k.now)

    @property
    def text(self) -> str:
        return "\n".join(self.said)

    def tree(self, folder: Path) -> dict[str, bytes]:
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


class CliCase(HiringCase):
    """The commands as they are typed. The release is signed with the kit's key; the plugin holds that key as its
    built-in one, so no variable is needed and no test catalog is in use unless a test sets one up."""

    def setUp(self) -> None:
        super().setUp()
        self.environ: dict[str, str] = {}
        self.opened: list[str] = []  # every address a catalog was opened at
        self.b64 = base64.b64encode(self.k.pub).decode()
        built_in = mock.patch.dict(keys.CATALOG_KEYS, {self.k.kid: self.b64}, clear=True)
        built_in.start()
        self.addCleanup(built_in.stop)

    def _open(self, base: str) -> DirSource:
        self.opened.append(base)
        return DirSource(self.release)

    def app(self, io: Io | None = None, chat: bool = False) -> commands.App:
        return commands.App(environ=self.environ, root=self.home, io=io or self.io, open_source=self._open,
                            now=self.k.now, chat=chat)

    def run_cli(self, *argv: str) -> int:
        parser = argparse.ArgumentParser(prog="hermes harnsy-hr")
        cli.setup_parser(parser)
        self.said.clear()
        return cli.run(parser.parse_args(argv), self.app())

    def run_slash(self, raw: str) -> str:
        with mock.patch.object(slash, "_app", lambda io: self.app(io, chat=True)):
            return slash.handle(raw)
