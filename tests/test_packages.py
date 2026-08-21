import io
import zipfile
from pathlib import Path

import unittest
import tempfile
from pathlib import Path

from app.packages import PackageError, inspect_directory, inspect_zip


def make_zip(files: dict[str, str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


class PackageInspectionTest(unittest.TestCase):
    def test_inspect_zip_finds_manifest_entrypoint(self):
        payload = make_zip({
            "manifest.yaml": "name: demo\nentrypoint: run.py\n",
            "run.py": "print('ok')\n",
            "requirements.txt": "requests==2.32.4\n",
        })

        result = inspect_zip(payload)

        self.assertEqual(result.name, "demo")
        self.assertEqual(result.entrypoint, "run.py")
        self.assertTrue(result.has_requirements)

    def test_inspect_zip_rejects_path_traversal(self):
        payload = make_zip({"../escape.py": "print('bad')\n"})

        with self.assertRaisesRegex(PackageError, "路径"):
            inspect_zip(payload)

    def test_inspect_zip_rejects_multiple_inferred_entries(self):
        payload = make_zip({"a.py": "pass\n", "b.py": "pass\n"})

        with self.assertRaisesRegex(PackageError, "入口"):
            inspect_zip(payload)

    def test_inspect_directory_accepts_zentao_script(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "zentao_bug_summary.py").write_text("print('ok')", encoding="utf-8")
            (source / "zentao_bug_analyzer.py").write_text("import json\n", encoding="utf-8")

            result = inspect_directory(source)

            self.assertEqual(result.entrypoint, "zentao_bug_summary.py")

    def test_inspect_directory_requires_external_dependencies_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "main.py").write_text("import requests\n", encoding="utf-8")

            with self.assertRaisesRegex(PackageError, "requirements"):
                inspect_directory(source)
