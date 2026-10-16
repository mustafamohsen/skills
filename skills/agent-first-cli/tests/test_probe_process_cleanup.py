"""Process lifetime tests through the public probe CLI, using temporary workers."""

import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "afcli_probe.py"


def wait_for_file(path, process, timeout=8):
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Process exited before fixture was ready: {process.returncode}")
        time.sleep(0.02)
    if not path.exists():
        raise AssertionError("Fixture did not become ready")


@unittest.skipUnless(os.name in ("posix", "nt"), "Requires POSIX process groups or Windows jobs")
class ProcessCleanupTests(unittest.TestCase):
    def test_timeout_stops_descendants_before_reporting_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            heartbeat = root / "heartbeat"
            worker = root / "worker.py"
            worker.write_text(
                "import time\nfrom pathlib import Path\n"
                f"path = Path({str(heartbeat)!r})\n"
                "deadline = time.monotonic() + 12\n"
                "while time.monotonic() < deadline:\n    path.write_text(str(time.monotonic_ns()))\n    time.sleep(0.05)\n"
            )
            cli = root / "cli.py"
            cli.write_text(
                "import subprocess, sys, time\n"
                f"subprocess.Popen([sys.executable, {str(worker)!r}], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "print('before-timeout', flush=True)\ntime.sleep(30)\n"
            )
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"name": "timeout", "effects": "read-only", "args": [], "timeout_seconds": 2}]}))
            process = subprocess.Popen(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]),
                 "--matrix", str(matrix), "--fail-on", "critical"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                wait_for_file(heartbeat, process)
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(stderr, "", stderr)
                self.assertEqual(process.returncode, 1)
                report = json.loads(stdout)
                self.assertTrue(any("timed out" in i["message"] for i in report["data"]["results"][0]["issues"]))
                snapshot = heartbeat.read_text()
                time.sleep(0.3)
                self.assertEqual(heartbeat.read_text(), snapshot, "Worker continued after timeout")
                self.assertIn("before-timeout", report["data"]["results"][0]["stdout_preview"])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                # A bounded worker lifetime ensures even a failing pre-fix test is safe.

    def test_exited_parent_does_not_leave_a_background_worker(self):
        self.check_worker_cleanup(interrupt=False)

    def test_interruption_stops_background_worker(self):
        self.check_worker_cleanup(interrupt=True)

    def check_worker_cleanup(self, interrupt):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            heartbeat = root / "heartbeat"
            worker = root / "worker.py"
            worker.write_text(
                "import time\nfrom pathlib import Path\n"
                f"path = Path({str(heartbeat)!r})\n"
                "deadline = time.monotonic() + 12\n"
                "while time.monotonic() < deadline:\n    path.write_text(str(time.monotonic_ns()))\n    time.sleep(0.05)\n"
            )
            cli = root / "cli.py"
            cli.write_text(
                "import subprocess, sys, time\nfrom pathlib import Path\n"
                f"subprocess.Popen([sys.executable, {str(worker)!r}], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                f"while not Path({str(heartbeat)!r}).exists(): time.sleep(0.01)\n"
                + ("time.sleep(30)\n" if interrupt else "print('done', flush=True)\n")
            )
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only", "timeout_seconds": 8}]}))
            process = subprocess.Popen(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]), "--matrix", str(matrix)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                wait_for_file(heartbeat, process)
                if interrupt:
                    process.terminate()
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(stderr, "", stderr)
                if not interrupt:
                    self.assertEqual(process.returncode, 0)
                    self.assertEqual(json.loads(stdout)["status"], "success")
                elif os.name == "posix":
                    self.assertEqual(process.returncode, 143)
                    self.assertEqual(json.loads(stdout)["error"]["code"], "INTERRUPTED")
                # Windows TerminateProcess closes the job handle even though
                # the runner itself cannot emit a report after forced termination.
                time.sleep(0.1)
                snapshot = heartbeat.read_text()
                time.sleep(0.3)
                self.assertEqual(heartbeat.read_text(), snapshot)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)

    def test_timeout_stops_grandchildren_holding_inherited_output_pipes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            worker = root / "worker.py"
            worker.write_text("import time\ntime.sleep(12)\n")
            launcher = root / "launcher.py"
            launcher.write_text(f"import subprocess, sys, time\nsubprocess.Popen([sys.executable, {str(worker)!r}])\ntime.sleep(12)\n")
            cli = root / "cli.py"
            cli.write_text(f"import subprocess, sys, time\nsubprocess.Popen([sys.executable, {str(launcher)!r}])\nprint('ready', flush=True)\ntime.sleep(12)\n")
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"tests": [{"args": [], "effects": "read-only", "timeout_seconds": 1}]}))
            started = time.monotonic()
            result = subprocess.run(
                [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]), "--matrix", str(matrix)],
                capture_output=True, text=True, timeout=8,
            )
            self.assertLess(time.monotonic() - started, 7)
            self.assertEqual(result.stderr, "", result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "partial")
            self.assertIn("ready", report["data"]["results"][0]["stdout_preview"])

    def test_stdin_is_closed_unless_the_matrix_supplies_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "cli.py"
            cli.write_text("import sys\nprint(repr(sys.stdin.read()), flush=True)\n")
            matrix = root / "matrix.json"
            for supplied, expected in ((None, "''"), ("matrix input", "'matrix input'")):
                with self.subTest(stdin=supplied):
                    test = {"args": [], "effects": "read-only", "timeout_seconds": 2}
                    if supplied is not None:
                        test["stdin"] = supplied
                    matrix.write_text(json.dumps({"tests": [test]}))
                    result = subprocess.run(
                        [sys.executable, str(PROBE), "--cmd", shlex.join([sys.executable, str(cli)]), "--matrix", str(matrix)],
                        input="ambient input", capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(json.loads(result.stdout)["data"]["results"][0]["stdout_preview"].strip(), expected)


if __name__ == "__main__":
    unittest.main()
