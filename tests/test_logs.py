import tempfile
import unittest
from pathlib import Path

from app.logs import read_log


class ExecutionLogTest(unittest.TestCase):
    def test_read_log_returns_content_inside_log_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run.log").write_text("hello\n", encoding="utf-8")

            self.assertEqual(read_log(root, "run.log"), "hello\n")

    def test_read_log_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                read_log(root, "..\\secret.log")
