"""Signed catalog releases for tests, with a key made for the test.

A bundle is packed the way the catalog's publisher does it (manifest.json first, signatures/catalog.jws last), so a
test can then break one thing.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import warnings
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HOST = "hr.harnsy.dev"
TESTDATA = Path(__file__).parent / "testdata"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def rfc3339(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def write(file: Path, b: bytes) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b)


def zip_bytes(order: list[str], files: dict[str, bytes], modes: dict[str, int] | None = None) -> bytes:
    """Files as a zip in the given order; a name that has no file is left out. modes sets a Unix mode per name."""
    buf = BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # a test may write one name twice
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name in order:
                if name not in files:
                    continue
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (modes or {}).get(name, 0o100644) << 16
                z.writestr(info, files[name])
    return buf.getvalue()


def unzip_all(file: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(file)) as z:
        return {i.filename: z.read(i) for i in z.infolist()}


@dataclass
class Packed:
    """A signed .harnsy file and its feed entry."""

    entry: dict
    file: bytes


class Kit:
    """A test catalog key and the moment the tests call «now»."""

    def __init__(self) -> None:
        self.priv = Ed25519PrivateKey.generate()
        self.kid = "t1"
        self.pub = self.priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.now = datetime(2026, 11, 12, 10, 0, 0, tzinfo=timezone.utc)

    @property
    def keys(self) -> dict[str, bytes]:
        return {self.kid: self.pub}

    def jws(self, kid: str, claims: dict, alg: str = "EdDSA") -> str:
        """signatures/catalog.jws for these claims."""
        head = b64u(json.dumps({"alg": alg, "kid": kid, "typ": "JWT"}).encode())
        body = head + "." + b64u(json.dumps(claims).encode())
        return body + "." + b64u(self.priv.sign(body.encode()))

    def pack(self, id: str, version: str, src: dict[str, bytes], edit=None) -> Packed:
        """The signed bundle of id@version from its files. A listing.json among them gives the card's title and tags
        and is not packed. edit may change the files right before they are zipped: after the manifest and the
        signature were made."""
        files = {n: b for n, b in src.items() if n != "listing.json"}
        listing = json.loads(src.get("listing.json", b"{}"))
        doc = json.loads(files["bundle.json"])
        manifest = {"format": "harnsy-bundle", "format_version": 1, "id": id, "version": version, "kind": "employee",
                    "publisher": id.split("/")[0], "created_at": rfc3339(self.now),
                    "files": {n: sha(b) for n, b in files.items()}}
        order = ["manifest.json", *sorted(files), "signatures/catalog.jws"]
        mb = json.dumps(manifest, indent=2).encode()
        files["manifest.json"] = mb
        files["signatures/catalog.jws"] = self.jws(self.kid, {"iss": HOST, "sub": id, "ver": version,
                                                              "manifest_sha256": sha(mb),
                                                              "iat": int(self.now.timestamp())}).encode()
        if edit:
            edit(files)
            order += [n for n in files if n not in order]
        file = zip_bytes(order, files)
        return Packed(card(id, version, doc, listing, file), file)

    def feed(self, packs: list[Packed]) -> dict:
        """The feed of these bundles: seq 7, good for a week from the kit's now."""
        return {"v": 1, "seq": 7, "expires": rfc3339(self.now + timedelta(days=7)),
                "bundles": [copy.deepcopy(p.entry) for p in packs], "revoked": []}

    def sign_feed(self, kid: str, feed: bytes) -> bytes:
        return json.dumps({"kid": kid, "sig": base64.b64encode(self.priv.sign(feed)).decode()}).encode()

    def release(self, dir: Path, packs: list[Packed], edit=None) -> None:
        """A release in dir: every bundle at its feed url, v1/feed.json and v1/feed.json.sig. edit may change the feed
        before it is signed."""
        feed = self.feed(packs)
        if edit:
            edit(feed)
        fb = json.dumps(feed, indent=2, ensure_ascii=False).encode()
        for p in packs:
            write(Path(dir) / p.entry["url"].removeprefix("https://" + HOST + "/"), p.file)
        write(Path(dir) / "v1" / "feed.json", fb)
        write(Path(dir) / "v1" / "feed.json.sig", self.sign_feed(self.kid, fb))

    def catalog(self, dir: Path) -> list[Packed]:
        """The newest version of every employee under dir (<publisher>/<name>/<version>/), in the order of their ids."""
        newest: dict[str, str] = {}
        for bj in Path(dir).glob("*/*/*/bundle.json"):
            publisher, name, version = bj.parent.relative_to(dir).parts
            id = publisher + "/" + name
            if id not in newest or _numbers(newest[id]) < _numbers(version):
                newest[id] = version
        return [self.pack(id, newest[id], source(Path(dir) / id / newest[id])) for id in sorted(newest)]


def _numbers(version: str) -> list[int]:
    return [int(x) for x in version.split(".")]


def card(id: str, version: str, doc: dict, listing: dict, file: bytes) -> dict:
    """The feed's card of a bundle, as the publisher writes it."""
    publisher = id.split("/")[0]
    role, name = doc.get("role", {}), doc.get("role", {}).get("name", "")
    entry = {"id": id, "kind": "employee", "version": version,
             "title": listing.get("title") or name[:1].upper() + name[1:], "summary": role.get("tagline", ""),
             "persona": {"name": doc.get("persona", {}).get("name", "")}, "department": role.get("department", ""),
             "industries": role.get("industries") or [], "tags": listing.get("tags") or [],
             "skills": [c["name"] for c in doc.get("competencies", []) if c.get("name")][:5],
             "keywords": role.get("keywords") or [], "published": "2026-10-08", "updated": "2026-11-01",
             "publisher_name": listing.get("publisher_name") or publisher,
             "url": f"https://{HOST}/packs/{id}/{version}.harnsy", "sha256": sha(file), "size": len(file),
             "publisher": publisher, "cv_url": f"https://{HOST}/e/{id}", "license": doc.get("license", ""),
             "attribution": doc.get("attribution") or []}
    if listing.get("license_note"):
        entry["license_note"] = listing["license_note"]
    return entry


def source(dir: Path) -> dict[str, bytes]:
    """A version folder (bundle.json, listing.json, docs/, skills/): every file by its path with forward slashes."""
    files = {p.relative_to(dir).as_posix(): p.read_bytes() for p in sorted(Path(dir).rglob("*")) if p.is_file()}
    return {n: b for n, b in files.items() if not n.startswith("avatar.")}


def sample(name: str) -> dict[str, bytes]:
    """A small employee with one skill."""
    doc = {
        "schema": "harnsy.employee/v1",
        "persona": {"name": "Vera", "character": "Calm and exact."},
        "role": {"name": name, "department": "engineering", "mandate": "Reviews Go code.",
                 "deliverable": "A verdict per change.", "prompt": "You are the " + name + ", an AI agent.",
                 "tagline": "Finds the race before it ships."},
        "competencies": [{"key": "review-go", "name": "Go review", "summary": "Reads a change for races."}],
        "license": "CC-BY-4.0",
        "skills": [{"name": "race-hunt", "description": "Find data races."}],
    }
    return {
        "bundle.json": json.dumps(doc, indent=2).encode(),
        "docs/persona-casebook.md": b"### C1. A race\n",
        "skills/race-hunt/SKILL.md": b"---\nname: race-hunt\ndescription: Find data races.\n---\nRun the race detector.\n",
    }
