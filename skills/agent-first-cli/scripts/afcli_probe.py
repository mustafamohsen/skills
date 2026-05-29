#!/usr/bin/env python3
"""Probe a live CLI for agent-first behavior.

This tool executes a matrix of CLI invocations and emits a JSON report. It is
not a replacement for project-specific tests; it is a fast contract probe for
parseability, channel discipline, exit codes, and non-interactive behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SEVERITY_ORDER = {"info": 0, "low": 1, "warning": 2, "high": 3, "critical": 4}
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(\s*[:=]\s*)([^\s\"',}]+)"),
    re.compile(r"(?i)(bearer\s+)([a-z0-9._\-]{12,})"),
    re.compile(r"(sk-[a-zA-Z0-9]{8,})"),
]


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 3:
            redacted = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}redacted", redacted)
        elif pattern.groups == 2:
            redacted = pattern.sub(lambda m: f"{m.group(1)}redacted", redacted)
        else:
            redacted = pattern.sub("redacted", redacted)
    return redacted


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... <truncated {len(text) - max_chars} chars>"


def add_issue(
    issues: List[Dict[str, Any]],
    severity: str,
    area: str,
    message: str,
    recommendation: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    item: Dict[str, Any] = {
        "severity": severity,
        "area": area,
        "message": message,
    }
    if recommendation:
        item["recommendation"] = recommendation
    if details:
        item["details"] = details
    issues.append(item)


def load_matrix(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {
            "tests": [
                {
                    "name": "version_json",
                    "args": ["version", "--output", "json"],
                    "expect_exit": [0],
                    "expect_json_stdout": True,
                    "expect_status": ["success"],
                    "timeout_seconds": 10,
                },
                {
                    "name": "capabilities_json",
                    "args": ["capabilities", "--output", "json"],
                    "expect_exit": [0],
                    "expect_json_stdout": True,
                    "expect_status": ["success"],
                    "timeout_seconds": 10,
                },
                {
                    "name": "bad_flag_json_error",
                    "args": ["--definitely-not-a-real-flag", "--output", "json"],
                    "expect_exit": [2, 12],
                    "expect_json_stdout": True,
                    "expect_status": ["error"],
                    "timeout_seconds": 10,
                },
            ]
        }
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Could not read matrix JSON: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("tests"), list):
        raise SystemExit("Matrix must be a JSON object with a `tests` array.")
    return value


def parse_json_stdout(stdout: str) -> Tuple[Optional[Any], Optional[str]]:
    stripped = stdout.strip()
    if not stripped:
        return None, "stdout is empty"
    try:
        return json.loads(stripped), None
    except json.JSONDecodeError as exc:
        return None, f"stdout is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"


def envelope_checks(obj: Any, expect_status: Optional[List[str]], expect_error_code: Optional[List[str]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if not isinstance(obj, dict):
        add_issue(issues, "critical", "json", "JSON stdout is not an object/envelope.")
        return issues

    status = obj.get("status")
    if status is None:
        add_issue(issues, "high", "json", "JSON envelope is missing top-level `status`.")
    elif status not in {"success", "partial", "error"}:
        add_issue(issues, "high", "json", "Top-level `status` is not one of success, partial, error.", details={"status": status})

    if expect_status and status not in expect_status:
        add_issue(
            issues,
            "critical",
            "json",
            "Top-level `status` did not match expectation.",
            details={"expected": expect_status, "actual": status},
        )

    if not obj.get("command"):
        add_issue(issues, "warning", "json", "JSON envelope is missing stable `command` field.")

    warnings = obj.get("warnings")
    if warnings is not None and not isinstance(warnings, list):
        add_issue(issues, "warning", "json", "`warnings` should be an array.")

    metadata = obj.get("metadata")
    if not isinstance(metadata, dict):
        add_issue(issues, "warning", "json", "JSON envelope is missing `metadata` object.")
    elif not metadata.get("schema_version"):
        add_issue(issues, "warning", "json", "`metadata.schema_version` is missing.")

    if status == "error" or expect_error_code:
        error = obj.get("error")
        if not isinstance(error, dict):
            add_issue(issues, "critical", "json", "Error result lacks structured `error` object.")
        else:
            code = error.get("code")
            if not code:
                add_issue(issues, "critical", "json", "Structured error is missing stable `error.code`.")
            if expect_error_code and code not in expect_error_code:
                add_issue(
                    issues,
                    "critical",
                    "json",
                    "`error.code` did not match expectation.",
                    details={"expected": expect_error_code, "actual": code},
                )
            if "recoverable" not in error:
                add_issue(issues, "warning", "json", "Structured error should include `recoverable`.")
    return issues


def run_one(base_cmd: List[str], test: Dict[str, Any], default_timeout: int, max_capture: int) -> Dict[str, Any]:
    name = str(test.get("name") or "unnamed")
    args = test.get("args") or []
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return {
            "name": name,
            "status": "error",
            "issues": [
                {
                    "severity": "critical",
                    "area": "matrix",
                    "message": "Test `args` must be an array of strings.",
                }
            ],
        }

    cmd = base_cmd + args
    timeout = int(test.get("timeout_seconds") or default_timeout)
    stdin = test.get("stdin")
    env = os.environ.copy()
    for key, value in (test.get("env") or {}).items():
        env[str(key)] = str(value)

    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    except FileNotFoundError as exc:
        return {
            "name": name,
            "status": "error",
            "command": cmd,
            "issues": [
                {
                    "severity": "critical",
                    "area": "execution",
                    "message": str(exc),
                    "recommendation": "Check the `--cmd` value and ensure the CLI is on PATH.",
                }
            ],
        }

    duration_ms = round((time.monotonic() - started) * 1000, 3)
    issues: List[Dict[str, Any]] = []

    if timed_out:
        add_issue(
            issues,
            "critical",
            "execution",
            "Command timed out; possible interactive prompt or hanging operation.",
            recommendation="Ensure agent mode is non-interactive and add timeout handling.",
            details={"timeout_seconds": timeout},
        )

    expect_exit = test.get("expect_exit")
    if expect_exit is not None:
        expected = [int(v) for v in expect_exit]
        if exit_code not in expected:
            add_issue(
                issues,
                "critical",
                "exit_code",
                "Exit code did not match expectation.",
                details={"expected": expected, "actual": exit_code},
            )

    if ANSI_RE.search(stdout):
        severity = "high" if test.get("expect_json_stdout") else "warning"
        add_issue(
            issues,
            severity,
            "stdout",
            "Standard output contains ANSI escape sequences.",
            recommendation="Disable color/decorative output in JSON or agent mode.",
        )

    expect_json = bool(test.get("expect_json_stdout"))
    parsed_json: Optional[Any] = None
    parse_error: Optional[str] = None
    if expect_json:
        parsed_json, parse_error = parse_json_stdout(stdout)
        if parse_error:
            add_issue(
                issues,
                "critical",
                "stdout",
                parse_error,
                recommendation="In `--output json` mode, stdout should contain exactly one JSON document.",
            )
        else:
            issues.extend(envelope_checks(parsed_json, test.get("expect_status"), test.get("expect_error_code")))
    elif stdout.strip().startswith("{") or stdout.strip().startswith("["):
        parsed_json, _ = parse_json_stdout(stdout)

    if bool(test.get("expect_stderr_empty")) and stderr.strip():
        add_issue(
            issues,
            "warning",
            "stderr",
            "Standard error was not empty despite expectation.",
        )

    status = "passed" if not issues else "failed"
    return {
        "name": name,
        "status": status,
        "command": cmd,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout_preview": truncate(redact(stdout), max_capture),
        "stderr_preview": truncate(redact(stderr), max_capture),
        "json_stdout_type": type(parsed_json).__name__ if parsed_json is not None else None,
        "issues": issues,
    }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    issue_counts = {sev: 0 for sev in SEVERITY_ORDER}
    total_issues = 0
    for result in results:
        for item in result.get("issues") or []:
            sev = item.get("severity", "info")
            issue_counts[sev] = issue_counts.get(sev, 0) + 1
            total_issues += 1
    return {
        "tests_total": len(results),
        "tests_passed": sum(1 for r in results if r.get("status") == "passed"),
        "tests_failed": sum(1 for r in results if r.get("status") != "passed"),
        "issue_count": total_issues,
        "counts_by_severity": issue_counts,
    }


def result_envelope(status: str, data: Dict[str, Any], error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "status": status,
        "command": "afcli.probe",
        "data": data,
        "warnings": [],
        "error": error,
        "metadata": {
            "tool_version": "1.0.0",
            "schema_version": "1.0",
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Probe a live CLI for agent-first behavior and emit a JSON report.")
    parser.add_argument("--cmd", required=True, help="Base command to run, for example: 'mytool' or 'python -m mytool'.")
    parser.add_argument("--matrix", help="Path to JSON probe matrix. Defaults to a minimal built-in matrix.")
    parser.add_argument("--out", help="Optional path to write JSON report. Defaults to stdout.")
    parser.add_argument("--timeout", type=int, default=10, help="Default per-test timeout in seconds.")
    parser.add_argument("--max-capture", type=int, default=4000, help="Maximum stdout/stderr preview chars per test.")
    parser.add_argument(
        "--fail-on",
        choices=["none", "warning", "high", "critical"],
        default="none",
        help="Exit non-zero if any issue at or above this severity exists.",
    )
    args = parser.parse_args(argv)

    base_cmd = shlex.split(args.cmd)
    if not base_cmd:
        envelope = result_envelope(
            "error",
            data={},
            error={
                "code": "INVALID_COMMAND",
                "message": "`--cmd` cannot be empty.",
                "details": {},
                "recoverable": True,
                "suggested_actions": ["Pass a base command such as `--cmd mytool`."],
            },
        )
        print(json.dumps(envelope, indent=2))
        return 2

    matrix = load_matrix(args.matrix)
    tests = matrix.get("tests") or []
    results = [run_one(base_cmd, test, args.timeout, args.max_capture) for test in tests]
    summary = summarize(results)
    status = "success" if summary["tests_failed"] == 0 else "partial"
    data = {
        "base_command": base_cmd,
        "matrix": args.matrix or "<built-in>",
        "summary": summary,
        "results": results,
    }
    envelope = result_envelope(status, data=data)
    output = json.dumps(envelope, indent=2, sort_keys=False)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    if args.fail_on != "none":
        threshold = SEVERITY_ORDER[args.fail_on]
        for result in results:
            for item in result.get("issues") or []:
                if SEVERITY_ORDER.get(item.get("severity", "info"), 0) >= threshold:
                    return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
