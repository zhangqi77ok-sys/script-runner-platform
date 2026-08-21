import tempfile
import unittest
from pathlib import Path

from app.storage import safe_child_path


class StoragePathTest(unittest.TestCase):
    def test_safe_child_path_stays_inside_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = safe_child_path(root, "task-1", "output.txt")
            self.assertEqual(path.parent, root / "task-1")

    def test_safe_child_path_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                safe_child_path(Path(directory), "..", "escape.txt")
