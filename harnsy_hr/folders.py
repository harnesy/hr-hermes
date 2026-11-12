"""Distribution folders on disk: written file by file, each inside the folder, nothing run."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .errors import Refusal
from .render import Tree

MANIFEST = "distribution.yaml"


def relative_files(tree: Tree) -> dict[str, bytes]:
    """The tree's files by their path inside the distribution folder."""
    return {path.removeprefix(tree.name + "/"): content for path, content in tree.files}


def write_tree(folder: Path, tree: Tree) -> None:
    """Writes the tree into a new folder. Every file is data: no file is made executable, none is run. A path that
    would land outside the folder stops the write (a gate of its own, after the checks on the bundle and the tree)."""
    folder.mkdir(parents=True)
    inside = folder.resolve()
    for rel, content in relative_files(tree).items():
        target = folder.joinpath(*rel.split("/"))
        if not target.parent.resolve().is_relative_to(inside) or target.name in ("", ".", ".."):
            remove(folder)  # checked before its folders are made: nothing appears outside
            raise Refusal("a file of the employee would land outside its folder: nothing was installed")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as f:  # a new file only: nothing is followed, nothing is overwritten
            f.write(content)
        os.chmod(target, 0o644)


def read_folder(folder: Path) -> dict[str, bytes]:
    """Every file under a folder by its path with forward slashes; empty when there is no folder."""
    if not folder.is_dir():
        return {}
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file() and not p.is_symlink()}


def holds(profile: Path, tree: Tree) -> bool:
    """Whether a profile folder holds this tree: every file byte for byte. The manifest is left out of the
    comparison, Hermes writes its own copy of it (with the source and the time)."""
    for rel, content in relative_files(tree).items():
        target = profile.joinpath(*rel.split("/"))
        try:
            same = rel == MANIFEST or (not target.is_symlink() and target.read_bytes() == content)
        except OSError:
            same = False
        if not same:
            return False
    return (profile / MANIFEST).is_file()


def installed_from(profile: Path, folder: Path) -> bool:
    """Whether the profile's manifest names our distribution folder as its source: it is the one this plugin
    installed, not a profile someone made under the same name."""
    try:
        return str(folder.resolve()) in (profile / MANIFEST).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def remove(folder: Path) -> None:
    """Removes a folder of ours, links not followed."""
    if folder.is_symlink():
        folder.unlink()
    elif folder.exists():
        shutil.rmtree(folder)
