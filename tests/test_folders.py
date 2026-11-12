"""Distribution folders: a file is written only inside the folder, and nothing is made outside it on the way."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from harnsy_hr import folders
from harnsy_hr.errors import Refusal
from harnsy_hr.render import Tree


def tree(*paths: str) -> Tree:
    return Tree(name="reviewer", soul=b"", notice="", files=[(p, b"text") for p in paths])


class WriteTreeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.profiles = Path(tmp.name) / "profiles"

    def test_a_tree_is_written_file_by_file(self) -> None:
        folder = self.profiles / "reviewer"
        folders.write_tree(folder, tree("reviewer/SOUL.md", "reviewer/skills/harnsy/a/SKILL.md"))
        self.assertEqual(folders.read_folder(folder), {"SOUL.md": b"text", "skills/harnsy/a/SKILL.md": b"text"})

    def test_a_path_that_leaves_the_folder_makes_nothing_outside_it(self) -> None:
        for path in ["reviewer/../outside/x", "reviewer/a/../../outside/b/x", "reviewer/../../outside/x"]:
            with self.assertRaises(Refusal, msg=path) as got:
                folders.write_tree(self.profiles / "reviewer", tree("reviewer/SOUL.md", path))
            self.assertIn("outside its folder", str(got.exception))
            self.assertEqual([p.name for p in self.profiles.iterdir()], [], path)
            self.assertEqual([p.name for p in self.profiles.parent.iterdir()], ["profiles"], path)


if __name__ == "__main__":
    unittest.main()
