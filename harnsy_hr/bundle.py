"""A .harnsy file: read within the format's limits and checked against the feed entry that names it."""

from __future__ import annotations

import hashlib
import stat
import zipfile
import zlib
from io import BytesIO

from . import grammar, jsonread, verify
from .errors import Refusal
from .types import Doc, Employee, Entry, Manifest

# Limits of bundle v1.
MAX_BUNDLE = 8 << 20  # a .harnsy file, and all its files unpacked
MAX_ZIP_FILES = 128  # entries in a .harnsy file

SIGNATURE_FILE = "signatures/catalog.jws"
_UNIX, _MACOS = 3, 19  # zip «made by» systems whose entries carry a Unix file mode
_DOS_SYSTEMS = (0, 11, 14)  # FAT, NTFS, VFAT: a folder is an attribute bit


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def clean_relative(name: str) -> bool:
    """Whether name is a clean relative path with forward slashes: no empty, `.` or `..` part, no backslash or NUL."""
    return bool(name) and "\\" not in name and "\x00" not in name and all(p not in ("", ".", "..") for p in name.split("/"))


def _regular(info: zipfile.ZipInfo) -> bool:
    """Whether a zip entry is a plain file: not a folder, a link, a device or a pipe."""
    if info.orig_filename.endswith("/"):
        return False
    if info.create_system in (_UNIX, _MACOS):
        return stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG)
    if info.create_system in _DOS_SYSTEMS:
        return not info.external_attr & 0x10
    return True


def unzip(file: bytes) -> dict[str, bytes]:
    """The files of a .harnsy file: at most MAX_ZIP_FILES entries, MAX_BUNDLE bytes unpacked whatever the headers say
    (counted by the bytes read), no name twice, no name that leaves the bundle, plain files only, stored or deflated
    (the two ways the format packs a file; no other is unpacked)."""
    try:
        with zipfile.ZipFile(BytesIO(file)) as z:
            entries = z.infolist()
            if len(entries) > MAX_ZIP_FILES:
                raise Refusal(f"{len(entries)} zip entries, at most {MAX_ZIP_FILES}")
            files, left = {}, MAX_BUNDLE
            for info in entries:
                name = info.orig_filename
                if name in files:
                    raise Refusal(f"{_shown(name)} is in the zip twice")
                if not clean_relative(name) or not _regular(info):
                    raise Refusal(f"zip entry {_shown(name)}: not a plain file inside the bundle")
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise Refusal(f"zip entry {_shown(name)}: not stored or deflated")
                with z.open(info) as member:
                    data = member.read(left + 1)
                left -= len(data)
                if left < 0:
                    raise Refusal(f"unpacks to more than {MAX_BUNDLE} bytes")
                files[name] = data
            return files
    except (zipfile.BadZipFile, zlib.error, NotImplementedError, RuntimeError, EOFError, OSError, ValueError) as err:
        raise Refusal(f"not a readable zip ({type(err).__name__})") from None


def _shown(name: str) -> str:
    """A name from a file, safe to print: nothing but its printable ASCII, cut short."""
    return '"' + "".join(c if " " <= c <= "~" else "?" for c in name[:120]) + '"'


def open_bundle(kid: str, pub: bytes, host: str, e: Entry, file: bytes) -> Employee:
    """Checks a .harnsy file against its feed entry (size, SHA-256, the manifest's names and file hashes, the catalog's
    signature over the manifest) and returns the employee. Only files the manifest lists are kept."""
    if len(file) != e.size or sha256(file) != e.sha256:
        raise Refusal("size or sha256 differs from the feed")
    everything = unzip(file)
    if "manifest.json" not in everything:
        raise Refusal("no manifest.json")
    mb = everything["manifest.json"]
    m = Manifest.read(mb)
    if (m.format, m.format_version, m.id, m.version, m.kind) != ("harnsy-bundle", 1, e.id, e.version, "employee"):
        raise Refusal(f"manifest names {_shown(m.id)[1:-1]}@{_shown(m.version)[1:-1]} "
                      f"({_shown(m.format)[1:-1]} v{m.format_version}, {_shown(m.kind)[1:-1]})")
    files = {}
    for name, digest in m.files.items():
        if not grammar.is_bundle_path(name):
            raise Refusal(f"{_shown(name)} is not a file a bundle carries")
        if name not in everything or name.startswith("signatures/") or sha256(everything[name]) != digest:
            raise Refusal(f"{name} missing or its sha256 differs")
        files[name] = everything[name]
    claims = verify.jws_claims(kid, pub, everything.get(SIGNATURE_FILE, b"").decode("utf-8", "replace"))
    w = "catalog.jws claims"
    jsonread.integer(claims, "iat", w)
    if (jsonread.text(claims, "iss", w), jsonread.text(claims, "sub", w), jsonread.text(claims, "ver", w),
            jsonread.text(claims, "manifest_sha256", w)) != (host, e.id, e.version, sha256(mb)):
        raise Refusal("catalog.jws claims do not match this bundle")
    if "bundle.json" not in files:
        raise Refusal("no bundle.json")
    return Employee(entry=e, manifest=m, manifest_sha256=sha256(mb), doc=Doc.read(files["bundle.json"]), files=files)
