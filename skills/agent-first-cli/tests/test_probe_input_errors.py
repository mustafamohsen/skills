"""Malformed inputs and outputs remain structured at the public CLI boundary."""

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "afcli_probe.py"
GOOD = {"status": "success", "command": "fixture", "metadata": {"schema_version": "1.0"}}


class ProbeInputTests(unittest.TestCase):
    def test_malformed_status_is_a_finding_and_later_tests_still_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            cli.write_text(
                "import json, sys\n"
                f"print(json.dumps({{'status': []}} if sys.argv[1] == 'bad' else {GOOD!r}))\n"
            )
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [
                {"name": name, "effects": "read-only", "args": [name], "expect_json_stdout": True}
                for name in ("bad", "good")
            ]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                 "--matrix", str(matrix), "--fail-on", "critical"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.stderr, "", result.stderr)
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "partial")
            self.assertEqual([r["status"] for r in report["data"]["results"]], ["failed", "passed"])

    def test_invalid_matrix_is_rejected_before_any_command_runs(self):
        invalid_tests = [None, [], "bad", {"args": "bad"}, {"args": [None]},
                         {"timeout_seconds": 0}, {"timeout_seconds": True}, {"stdin": 42},
                         {"env": []}, {"env": {"BAD=KEY": "x"}}, {"env": {"KEY": "\u0000"}},
                         {"expect_exit": [True]}, {"expect_status": "success"},
                         {"expect_json_stdout": "yes"}, {"expect_error_code": [1]}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "executed"
            cli = root / "cli.py"
            cli.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
            matrix = root / "matrix.json"
            for invalid in invalid_tests:
                with self.subTest(invalid=invalid):
                    marker.unlink(missing_ok=True)
                    matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only"}, invalid]}))
                    result = subprocess.run(
                        [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]), "--matrix", str(matrix)],
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertFalse(marker.exists())
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stderr, "", result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(report["error"]["code"], "MATRIX_INVALID")
                    self.assertIn("$.tests[1]", report["error"]["details"]["path"])

    def test_invalid_utf8_is_a_finding_and_later_tests_still_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            cli.write_text(
                "import json, os, sys\n"
                "if sys.argv[1] == 'bad': os.write(1, b'\\xff')\n"
                f"else: print(json.dumps({GOOD!r}))\n"
            )
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [
                {"name": name, "effects": "read-only", "args": [name], "expect_json_stdout": True}
                for name in ("bad", "good")
            ]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                 "--matrix", str(matrix), "--fail-on", "critical"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.stderr, "", result.stderr)
            self.assertEqual(result.returncode, 1)
            results = json.loads(result.stdout)["data"]["results"]
            self.assertEqual([r["status"] for r in results], ["error", "passed"])
            self.assertEqual(results[0]["issues"][0]["area"], "execution")

    def test_malformed_envelope_fields_are_findings_not_silent_passes(self):
        invalid = [
            {"status": {}}, {"status": None}, {"command": ["not-a-name"]},
            {"warnings": {}}, {"metadata": []}, {"metadata": {"schema_version": [1]}},
            {"status": "error", "error": {"code": ["BAD"], "recoverable": True}},
            {"status": "error", "error": {"code": "BAD", "recoverable": "yes"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only", "expect_json_stdout": True}]}))
            for changes in invalid:
                with self.subTest(changes=changes):
                    cli.write_text(f"print({json.dumps({**GOOD, **changes})!r})\n")
                    result = subprocess.run(
                        [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]), "--matrix", str(matrix)],
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.stderr, "", result.stderr)
                    self.assertEqual(json.loads(result.stdout)["status"], "partial")

    def test_invalid_json_variants_are_findings_and_do_not_abort_the_matrix(self):
        invalid_outputs = [json.dumps({**GOOD, "value": float("nan")}), '[' * 20000 + '0' + ']' * 20000]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [
                {"args": [name], "effects": "read-only", "expect_json_stdout": True} for name in ("bad", "good")
            ]}))
            for output in invalid_outputs:
                with self.subTest(output=output[:50]):
                    cli.write_text(f"import sys\nprint({output!r} if sys.argv[1] == 'bad' else {json.dumps(GOOD)!r})\n")
                    result = subprocess.run(
                        [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]), "--matrix", str(matrix)],
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.stderr, "", result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(report["status"], "partial")
                    self.assertEqual([r["status"] for r in report["data"]["results"]], ["failed", "passed"])
                    if "NaN" in output:
                        self.assertEqual(report["data"]["results"][0]["issues"][0]["area"], "stdout")

    def test_usage_and_matrix_errors_emit_json_without_tracebacks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_json = root / "invalid.json"
            invalid_json.write_text("{")
            wrong_shape = root / "wrong-shape.json"
            wrong_shape.write_text('{"tests": []}')
            cases = [
                ([], "INVALID_USAGE"),
                (["--cmd", "'"], "INVALID_COMMAND"),
                (["--cmd", "unused", "--timeout", "0"], "INVALID_USAGE"),
                (["--cmd", "unused", "--max-capture", "-1"], "INVALID_USAGE"),
                (["--cmd", "unused", "--matrix", str(root / "missing")], "MATRIX_READ_FAILED"),
                (["--cmd", "unused", "--matrix", str(invalid_json)], "MATRIX_READ_FAILED"),
                (["--cmd", "unused", "--matrix", str(wrong_shape)], "MATRIX_INVALID"),
            ]
            for arguments, code in cases:
                with self.subTest(code=code, arguments=arguments):
                    result = subprocess.run([sys.executable, str(PROBE), *arguments], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stderr, "", result.stderr)
                    self.assertEqual(json.loads(result.stdout)["error"]["code"], code)

    def test_unwritable_report_destination_emits_structured_error_on_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only"}]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, "-c", "pass"]),
                 "--matrix", str(matrix), "--out", str(root)], capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.stderr, "", result.stderr)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "REPORT_WRITE_FAILED")

    def test_execution_errors_are_reported_per_test(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only"}] * 2}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.quote(str(root)), "--matrix", str(matrix), "--fail-on", "critical"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "", result.stderr)
            results = json.loads(result.stdout)["data"]["results"]
            self.assertEqual([r["status"] for r in results], ["error", "error"])

    def test_valid_report_still_honors_output_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / "matrix.json"
            output = root / "report.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only", "future_field": {"enabled": True}}]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, "-c", "pass"]),
                 "--matrix", str(matrix), "--out", str(output)], capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
            self.assertEqual(json.loads(output.read_text())["status"], "success")


if __name__ == "__main__":
    unittest.main()
