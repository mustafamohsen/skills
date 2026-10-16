"""Black-box authorization tests using disposable local CLI resources."""

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "afcli_probe.py"


class MutationSafetyTests(unittest.TestCase):
    def test_unclassified_test_blocks_entire_matrix_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "executed"
            cli = root / "cli.py"
            cli.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [
                {"name": "first", "args": [], "effects": "read-only"},
                {"name": "unclassified", "args": []},
            ]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                 "--matrix", str(matrix)], capture_output=True, text=True, timeout=10,
            )
            self.assertFalse(marker.exists(), "Preflight must run before any test")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, "")
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "SAFETY_CLASSIFICATION_REQUIRED")

    def test_mutations_require_both_opt_in_and_isolated_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "disposable-resource"
            cli = root / "cli.py"
            cli.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [
                {"name": "apply_without_confirmation", "args": ["--mode", "apply"], "effects": "mutating"},
            ]}))
            command = [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                       "--matrix", str(matrix)]
            for flags in ([], ["--allow-mutations"], ["--isolated-environment", "local-fixture"],
                          ["--allow-mutations", "--isolated-environment", "   "]):
                with self.subTest(flags=flags):
                    result = subprocess.run(command + flags, capture_output=True, text=True, timeout=10)
                    self.assertFalse(marker.exists())
                    self.assertEqual(result.returncode, 6)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(json.loads(result.stdout)["error"]["code"], "UNSAFE_OPERATION")
            result = subprocess.run(command + ["--allow-mutations", "--isolated-environment", "local-fixture"],
                                    capture_output=True, text=True, timeout=10)
            self.assertTrue(marker.exists())
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "success")

    def test_only_explicit_read_only_classification_runs_without_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / "matrix.json"
            for effects in ("read-only", "readonly", None, [], {}, True):
                with self.subTest(effects=effects):
                    matrix.write_text(json.dumps({"tests": [{"args": [], "effects": effects}]}))
                    result = subprocess.run(
                        [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, "-c", "pass"]),
                         "--matrix", str(matrix)], capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0 if effects == "read-only" else 2)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(json.loads(result.stdout)["status"], "success" if effects == "read-only" else "error")


if __name__ == "__main__":
    unittest.main()
