"""What an id, a version and a file name of the catalog may look like.

The rules are the catalog publisher's own. A signed feed is authentic, not validated: everything here is checked
again on the person's machine before it becomes a path, a command argument or a line of YAML.
"""

from __future__ import annotations

import re

from .errors import Refusal

_PART = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")  # each half of an id: <publisher>/<name>
_SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_AVATAR = re.compile(r"avatar\.(png|jpe?g|webp)")
_SKILL = re.compile(r"[a-z0-9-]{1,40}")
_SKILL_FILE = re.compile(r"[A-Za-z0-9._-]{1,64}")
_SKILL_FOLDERS = ("scripts", "references", "assets")
# Device names Windows opens instead of a file, with any extension.
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

# Hermes Agent's own rule for a profile name, and the names it keeps for itself.
_PROFILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
RESERVED_PROFILES = frozenset({"hermes", "default", "test", "tmp", "root", "sudo"})

CASEBOOK = "docs/persona-casebook.md"


def is_id(id: str) -> bool:
    publisher, slash, name = id.partition("/")
    return bool(slash and _PART.fullmatch(publisher) and _PART.fullmatch(name))


def split_id(id: str) -> tuple[str, str]:
    """The publisher and the name of an id. What was given is not repeated in the refusal."""
    if not is_id(id):
        raise Refusal("not an id: an id is <publisher>/<name> in lowercase latin letters, digits and -, "
                      "for example harnsy/accountant")
    publisher, _, name = id.partition("/")
    return publisher, name


def is_version(version: str) -> bool:
    return bool(_SEMVER.fullmatch(version))


def _skill_file(name: str) -> bool:
    """A file name inside a skill's folder: a portable name no file system reads as another."""
    return bool(_SKILL_FILE.fullmatch(name)) and not name.startswith(".") and not name.endswith(".") \
        and name.split(".")[0].upper() not in _WINDOWS_RESERVED and name.lower() != "skill.md"


def is_bundle_path(path: str) -> bool:
    """Whether a path of a bundle's manifest has one of the shapes a bundle may hold."""
    if path in ("bundle.json", CASEBOOK) or _AVATAR.fullmatch(path):
        return True
    parts = path.split("/")
    if parts[0] != "skills" or len(parts) not in (3, 4) or not _SKILL.fullmatch(parts[1]):
        return False
    if len(parts) == 3:
        return parts[2] in ("SKILL.md", "LICENSE")
    return parts[2] in _SKILL_FOLDERS and _skill_file(parts[3])


def profile_name_fault(name: str) -> str:
    """Why Hermes would not take this profile name; empty when it would."""
    if not _PROFILE.fullmatch(name):
        return "a profile name is lowercase latin letters, digits, - and _, at most 64, and starts with a letter or digit"
    if name in RESERVED_PROFILES:
        return f"Hermes keeps the name {name} for itself"
    return ""
