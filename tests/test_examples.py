import tempfile
import unittest
from pathlib import Path

from app.executor import run_in_docker
from app.packages import inspect_directory


ROOT = Path(__file__).resolve().parents[1]


class ExampleExecutionTest(unittest.TestCase):
    def execute(self, name: str, timeout: int = 30, network: bool = False, environment=None):
        source = ROOT / "examples" / name
        info = inspect_directory(source)
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "run.log"
            code = run_in_docker(source, info.entrypoint, timeout, log, network, environment=environment)
            return code, log.read_text(encoding="utf-8", errors="replace")

    def test_hello_world_succeeds(self):
        code, log = self.execute("hello-world")
        self.assertEqual(code, 0)
        self.assertIn("hello from isolated sandbox", log)

    def test_artifact_writer_succeeds(self):
        code, log = self.execute("artifact-writer")
        self.assertEqual(code, 0)
        self.assertIn("artifact=result.txt", log)

    def test_environment_is_injected(self):
        code, log = self.execute("env-reader", environment={"SCRIPT_PLATFORM_TEST_VALUE": "visible"})
        self.assertEqual(code, 0)
        self.assertIn("value=visible", log)

    def test_failure_is_recorded(self):
        code, log = self.execute("failure")
        self.assertNotEqual(code, 0)
        self.assertIn("intentional failure", log)

    def test_timeout_is_enforced(self):
        with self.assertRaises(RuntimeError):
            self.execute("timeout", timeout=2)

    def test_network_is_available_only_when_enabled(self):
        disabled_code, _ = self.execute("network", timeout=20, network=False)
        enabled_code, enabled_log = self.execute("network", timeout=20, network=True)
        self.assertNotEqual(disabled_code, 0)
        self.assertEqual(enabled_code, 0)
        self.assertIn("status=200", enabled_log)
