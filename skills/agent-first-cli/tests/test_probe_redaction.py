"""Report redaction at the public CLI boundary; all secrets are synthetic."""

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "afcli_probe.py"


class ReportRedactionTests(unittest.TestCase):
    def test_nested_json_credentials_are_redacted_in_stdout_and_file_reports(self):
        secrets = ["FAKE-password with spaces", "FAKE-access-token", "FAKE-cookie"]
        payload = {"status": "success", "command": "fixture", "metadata": {"schema_version": "1.0"},
                   "data": {"password": secrets[0], "rows": [{"access_token": secrets[1]}],
                            "cookies": [secrets[2]], "public": "visible"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            cli.write_text(f"print({json.dumps(payload)!r})\n")
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only", "expect_json_stdout": True}]}))
            for to_file in (False, True):
                with self.subTest(to_file=to_file):
                    output = root / "report.json"
                    args = [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                            "--matrix", str(matrix)]
                    if to_file:
                        args.extend(["--out", str(output)])
                    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stderr, "")
                    text = output.read_text() if to_file else result.stdout
                    for secret in secrets:
                        self.assertNotIn(secret, text)
                    report = json.loads(text)
                    self.assertEqual(report["data"]["results"][0]["status"], "passed")
                    self.assertIn("visible", report["data"]["results"][0]["stdout_preview"])

    def test_argv_and_environment_secrets_are_removed_from_every_report_field(self):
        import os

        secrets = ["FAKE-base-password", "FAKE-test-token", "FAKE-env-secret", "FAKE-custom-option"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            cli.write_text(
                "import json, os, sys\n"
                "print(json.dumps({'status': os.environ['TEST_API_KEY'], 'command': 'fixture', "
                "'metadata': {'schema_version': '1.0'}}))\n"
                "print(sys.argv[-1], file=sys.stderr)\n"
            )
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{
                "name": secrets[1], "effects": "read-only", "args": ["--token=" + secrets[1], "--login", secrets[3]],
                "env": {"TEST_API_KEY": secrets[2]}, "expect_json_stdout": True, "expect_status": ["success"],
            }]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli), "--password", secrets[0]]),
                 "--matrix", str(matrix), "--sensitive-option=--login"],
                capture_output=True, text=True, timeout=10,
                env={**os.environ, "SYNTHETIC_SESSION_TOKEN": "FAKE-ambient-token"},
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "partial")
            for secret in secrets:
                self.assertNotIn(secret, result.stdout)
            self.assertIn("--password", report["data"]["base_command"])
            self.assertIn("redacted", report["data"]["base_command"])

    def test_quoted_logs_and_multiline_private_keys_are_redacted(self):
        secrets = ["FAKE-log password spaces", "FAKE-cookie-one", "FAKE-cookie-two", "FAKE-private-body"]
        logs = ('prefix {"password": "' + secrets[0] + '"}\n'
                'Cookie: session=' + secrets[1] + '; refresh=' + secrets[2] + '\n'
                '-----BEGIN PRIVATE KEY-----\n' + secrets[3] + '\n-----END PRIVATE KEY-----')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            cli.write_text(f"import sys\nprint({logs!r}, file=sys.stderr)\n")
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only"}]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                 "--matrix", str(matrix)], capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            for secret in secrets:
                self.assertNotIn(secret, result.stdout)
            json.loads(result.stdout)

    def test_redaction_precedes_truncation_and_covers_issue_details(self):
        secret = "FAKE-truncation-secret-" + "x" * 200
        payload = {"status": secret, "password": secret}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            cli.write_text(f"print({json.dumps(payload)!r})\n")
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only", "expect_json_stdout": True}]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                 "--matrix", str(matrix), "--max-capture", "60"], capture_output=True, text=True, timeout=10,
            )
            self.assertNotIn("FAKE-truncation", result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "partial")

    def test_missing_executable_report_does_not_echo_secret_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": ["--token", "FAKE-missing-token"], "effects": "read-only"}]}))
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", str(root / "missing-executable"), "--matrix", str(matrix)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertNotIn("FAKE-missing-token", result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "partial")


if __name__ == "__main__":
    unittest.main()
