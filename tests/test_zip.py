"""A .harnsy file is a zip within the format's limits: plain files inside the bundle, stored or deflated."""

from __future__ import annotations

import zipfile

from harnsy_hr.bundle import MAX_BUNDLE, MAX_ZIP_FILES, unzip
from harnsy_hr.errors import Refusal
from tests import kit
from tests.kit import sample, sha
from tests.test_catalog import Case, load


class UnsafeZipTest(Case):
    """A bundle whose zip breaks the format's limits is refused even when the feed names its hash."""

    def zipped(self, order, files, modes=None, method=zipfile.ZIP_DEFLATED) -> None:
        p = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer"))
        p.file = kit.zip_bytes(order, files, modes, method)
        p.entry["size"], p.entry["sha256"] = len(p.file), sha(p.file)
        self.k.release(self.dir, [p])

    def test_a_name_that_climbs_out(self) -> None:
        self.zipped(["manifest.json", "../../etc/cron.d/x"], {"manifest.json": b"{}", "../../etc/cron.d/x": b"x"})
        self.refused("not a plain file inside the bundle")

    def test_names_that_are_no_clean_relative_path(self) -> None:
        for name in ["/etc/passwd", "a\\b", "a/../b", "./a", "a//b", "a/", ".."]:
            self.zipped([name], {name: b"x"})
            self.refused("not a plain file inside the bundle")

    def test_a_link_or_a_folder(self) -> None:
        for mode in [0o120777, 0o040755, 0o010644]:
            self.zipped(["a"], {"a": b"manifest.json"}, {"a": mode})
            self.refused("not a plain file inside the bundle")

    def test_a_name_twice(self) -> None:
        self.zipped(["bundle.json", "bundle.json"], {"bundle.json": b"{}"})
        self.refused("in the zip twice")

    def test_more_than_it_may_unpack_to(self) -> None:
        big = b"a" * (MAX_BUNDLE // 2 + 1)
        self.zipped(["a", "b"], {"a": big, "b": big})
        self.refused("unpacks to more than")

    def test_too_many_entries(self) -> None:
        names = [f"f{i}" for i in range(MAX_ZIP_FILES + 1)]
        self.zipped(names, dict.fromkeys(names, b"x"))
        self.refused("zip entries")

    def test_not_a_zip(self) -> None:
        p = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer"))
        p.file = b"not a zip at all"
        p.entry["size"], p.entry["sha256"] = len(p.file), sha(p.file)
        self.k.release(self.dir, [p])
        self.refused("harnsy/reviewer@1.0.0")

    def test_a_bundle_file_above_the_limit_is_not_read(self) -> None:
        p = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer"))
        p.file = b"\0" * (MAX_BUNDLE + 1)
        p.entry["size"], p.entry["sha256"] = len(p.file), sha(p.file)
        self.k.release(self.dir, [p])
        self.refused("more than")

    def test_an_entry_packed_another_way_than_stored_or_deflated(self) -> None:
        for method in [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA]:
            self.zipped(["manifest.json"], {"manifest.json": b"{}"}, method=method)
            self.refused('harnsy/reviewer@1.0.0: zip entry "manifest.json": not stored or deflated')
            with self.assertRaises(Refusal) as got:
                unzip(kit.zip_bytes(["a", "b"], {"a": b"x", "b": b"y" * 100}, method=method))
            self.assertEqual(str(got.exception), 'zip entry "a": not stored or deflated')

    def test_stored_and_deflated_entries_unpack(self) -> None:
        files = {"a": b"x", "b": b"y" * 100}
        for method in [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED]:
            self.assertEqual(unzip(kit.zip_bytes(["a", "b"], files, method=method)), files)
        packed = self.k.pack("harnsy/reviewer", "1.0.0", sample("reviewer"))
        packed.file = kit.zip_bytes(list(kit.unzip_all(packed.file)), kit.unzip_all(packed.file), method=zipfile.ZIP_STORED)
        packed.entry["size"], packed.entry["sha256"] = len(packed.file), sha(packed.file)
        self.k.release(self.dir, [packed])
        self.assertEqual([e.entry.id for e in load(self.k, self.dir)[1]], ["harnsy/reviewer"])
