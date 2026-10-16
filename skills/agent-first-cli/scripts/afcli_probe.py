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

from afcli_process import ContainmentError, ProcessInterrupted, run_command

SEVERITY_ORDER = {"info": 0, "low": 1, "warning": 2, "high": 3, "critical": 4}
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"(?im)^(authorization|cookie|set-cookie)(\s*:\s*)([^\r\n]+)"),
    re.compile(r'''(?i)(["']?[\w.-]*(?:api[_-]?key|access[_-]?key|token|secret|password|passwd|authorization|cookie|credential|private[_-]?key)[\w.-]*["']?)(\s*[:=]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s"',}]+)'''),
    re.compile(r"(?i)(bearer\s+)([^\s\"',}]+)"),
    re.compile(r"(sk-[a-zA-Z0-9]{8,})"),
]


def sensitive_name(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    return any(part in normalized for part in (
        "password", "passwd", "token", "secret", "apikey", "accesskey",
        "authorization", "cookie", "credential", "privatekey",
    ))


def collect_secrets(value: Any, secrets: set[str], sensitive: bool = False) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            collect_secrets(item, secrets, sensitive or sensitive_name(key))
    elif isinstance(value, list):
        for item in value:
            collect_secrets(item, secrets, sensitive)
    elif isinstance(value, str) and sensitive and value:
        secrets.add(value)


def collect_argument_secrets(arguments: List[str], secrets: set[str], extra_options: List[str]) -> None:
    take_next = False
    for argument in arguments:
        if take_next:
            if argument:
                secrets.add(argument)
            take_next = False
        elif argument.startswith("-"):
            name, separator, value = argument.partition("=")
            if sensitive_name(name) or name in extra_options:
                if separator and value:
                    secrets.add(value)
                elif not separator:
                    take_next = True


def redact_data(value: Any, secrets: Optional[set[str]] = None) -> Any:
    if isinstance(value, dict):
        return {redact(key, secrets): "redacted" if sensitive_name(key) else redact_data(item, secrets)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_data(item, secrets) for item in value]
    if isinstance(value, str):
        return redact(value, secrets)
    return value


def redact(text: str, secrets: Optional[set[str]] = None) -> str:
    if text.lstrip().startswith(("{", "[")):
        try:
            return json.dumps(redact_data(json.loads(text), secrets))
        except (ValueError, RecursionError):
            pass
    redacted = text
    for secret in sorted(secrets or (), key=len, reverse=True):
        redacted = redacted.replace(secret, "redacted")
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


class ProbeInputError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None, exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.exit_code = exit_code


class ProbeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's message can echo a credential supplied as an invalid flag.
        raise ProbeInputError("INVALID_USAGE", "Invalid probe arguments; see --help.")


def valid_text(value: Any, allow_nul: bool = False) -> bool:
    if not isinstance(value, str) or (not allow_nul and "\x00" in value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def validate_matrix(matrix: Any) -> None:
    def require(condition: bool, path: str, expected: str) -> None:
        if not condition:
            raise ProbeInputError("MATRIX_INVALID", f"Expected {expected}.", {"path": path})

    require(isinstance(matrix, dict), "$", "an object")
    tests = matrix.get("tests")
    require(isinstance(tests, list) and bool(tests), "$.tests", "a non-empty array")
    for index, test in enumerate(tests):
        path = f"$.tests[{index}]"
        require(isinstance(test, dict), path, "an object")
        if "name" in test:
            require(valid_text(test["name"]) and bool(test["name"].strip()), path + ".name", "a nonblank string")
        if "args" in test:
            require(isinstance(test["args"], list) and all(valid_text(arg) for arg in test["args"]),
                    path + ".args", "an array of NUL-free UTF-8 strings")
        if "stdin" in test:
            require(valid_text(test["stdin"], allow_nul=True), path + ".stdin", "a UTF-8 string")
        if "timeout_seconds" in test:
            value = test["timeout_seconds"]
            require(type(value) is int and value > 0, path + ".timeout_seconds", "a positive integer")
        for field in ("expect_json_stdout", "expect_stderr_empty"):
            if field in test:
                require(isinstance(test[field], bool), path + "." + field, "a boolean")
        for field in ("expect_exit", "expect_status", "expect_error_code"):
            if field not in test:
                continue
            values = test[field]
            require(isinstance(values, list) and bool(values), path + "." + field, "a non-empty array")
            if field == "expect_exit":
                require(all(type(value) is int for value in values), path + "." + field, "integer exit codes")
            else:
                require(all(valid_text(value) and bool(value) for value in values), path + "." + field, "non-empty strings")
                if field == "expect_status":
                    require(all(value in ("success", "partial", "error") for value in values),
                            path + "." + field, "success, partial, or error statuses")
        if "env" in test:
            env = test["env"]
            require(isinstance(env, dict), path + ".env", "an object")
            require(all(valid_text(key) and bool(key) and "=" not in key and valid_text(value)
                        for key, value in env.items()), path + ".env", "valid environment names and string values")


def reject_nonfinite(value: str) -> None:
    raise ValueError("Non-finite numbers are not valid JSON.")


def load_matrix(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {
            "tests": [
                {
                    "name": "version_json",
                    "effects": "read-only",
                    "args": ["version", "--output", "json"],
                    "expect_exit": [0],
                    "expect_json_stdout": True,
                    "expect_status": ["success"],
                    "timeout_seconds": 10,
                },
                {
                    "name": "capabilities_json",
                    "effects": "read-only",
                    "args": ["capabilities", "--output", "json"],
                    "expect_exit": [0],
                    "expect_json_stdout": True,
                    "expect_status": ["success"],
                    "timeout_seconds": 10,
                },
                {
                    "name": "bad_flag_json_error",
                    "effects": "read-only",
                    "args": ["--definitely-not-a-real-flag", "--output", "json"],
                    "expect_exit": [2, 12],
                    "expect_json_stdout": True,
                    "expect_status": ["error"],
                    "timeout_seconds": 10,
                },
            ]
        }
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_nonfinite)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProbeInputError("MATRIX_READ_FAILED", "Could not read matrix JSON.",
                              {"error_type": type(exc).__name__}) from exc
    validate_matrix(value)
    return value


def parse_json_stdout(stdout: str) -> Tuple[Optional[Any], Optional[str]]:
    stripped = stdout.strip()
    if not stripped:
        return None, "stdout is empty"
    try:
        return json.loads(stripped, parse_constant=reject_nonfinite), None
    except json.JSONDecodeError as exc:
        return None, f"stdout is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"
    except (ValueError, RecursionError) as exc:
        return None, f"stdout cannot be parsed as standard JSON ({type(exc).__name__})"


def envelope_checks(obj: Any, expect_status: Optional[List[str]], expect_error_code: Optional[List[str]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if not isinstance(obj, dict):
        add_issue(issues, "critical", "json", "JSON stdout is not an object/envelope.")
        return issues

    status = obj.get("status")
    if status is None:
        add_issue(issues, "high", "json", "JSON envelope is missing top-level `status`.")
    elif not isinstance(status, str) or status not in {"success", "partial", "error"}:
        add_issue(issues, "critical", "json", "Top-level `status` must be a string: success, partial, or error.", details={"status": status})

    if expect_status and status not in expect_status:
        add_issue(
            issues,
            "critical",
            "json",
            "Top-level `status` did not match expectation.",
            details={"expected": expect_status, "actual": status},
        )

    if not isinstance(obj.get("command"), str) or not obj["command"]:
        add_issue(issues, "warning", "json", "JSON envelope requires a non-empty string `command` field.")

    warnings = obj.get("warnings")
    if warnings is not None and not isinstance(warnings, list):
        add_issue(issues, "warning", "json", "`warnings` should be an array.")

    metadata = obj.get("metadata")
    if not isinstance(metadata, dict):
        add_issue(issues, "warning", "json", "JSON envelope is missing `metadata` object.")
    elif not isinstance(metadata.get("schema_version"), str) or not metadata["schema_version"]:
        add_issue(issues, "warning", "json", "`metadata.schema_version` must be a non-empty string.")

    if status == "error" or expect_error_code:
        error = obj.get("error")
        if not isinstance(error, dict):
            add_issue(issues, "critical", "json", "Error result lacks structured `error` object.")
        else:
            code = error.get("code")
            if not isinstance(code, str) or not code:
                add_issue(issues, "critical", "json", "Structured error requires a non-empty string `error.code`.")
            if expect_error_code and code not in expect_error_code:
                add_issue(
                    issues,
                    "critical",
                    "json",
                    "`error.code` did not match expectation.",
                    details={"expected": expect_error_code, "actual": code},
                )
            if not isinstance(error.get("recoverable"), bool):
                add_issue(issues, "warning", "json", "Structured error should include boolean `recoverable`.")
    return issues


def run_one(base_cmd: List[str], test: Dict[str, Any], default_timeout: int, max_capture: int,
            secrets: Optional[set[str]] = None) -> Dict[str, Any]:
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
        proc = run_command(cmd, stdin=stdin, timeout=timeout, env=env)
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    except (OSError, UnicodeError, ValueError, OverflowError) as exc:
        return {
            "name": name,
            "status": "error",
            "command": cmd,
            "issues": [
                {
                    "severity": "critical",
                    "area": "execution",
                    "message": "Command execution or output decoding failed.",
                    "details": {"error_type": type(exc).__name__},
                    "recommendation": "Check command availability, permissions, UTF-8 output, and input limits.",
                }
            ],
        }

    if secrets is None:
        secrets = set()
    for captured in (stdout, stderr):
        try:
            collect_secrets(json.loads(captured), secrets)
        except (ValueError, RecursionError):
            pass

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
        "stdout_preview": truncate(redact(stdout, secrets), max_capture),
        "stderr_preview": truncate(redact(stderr, secrets), max_capture),
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


def probe_main(argv: Optional[List[str]] = None) -> int:
    parser = ProbeArgumentParser(description="Probe a live CLI for agent-first behavior and emit a JSON report.")
    parser.add_argument("--cmd", required=True, help="Base command to run, for example: 'mytool' or 'python -m mytool'.")
    parser.add_argument("--matrix", help="Path to JSON probe matrix. Defaults to a minimal built-in matrix.")
    parser.add_argument("--allow-mutations", action="store_true", help="Authorize mutating tests against disposable resources only.")
    parser.add_argument("--isolated-environment", help="Identify the verified isolated test environment; this is an attestation, not a sandbox.")
    parser.add_argument("--out", help="Optional path to write JSON report. Defaults to stdout.")
    parser.add_argument("--timeout", type=int, default=10, help="Default per-test timeout in seconds.")
    parser.add_argument("--max-capture", type=int, default=4000, help="Maximum stdout/stderr preview chars per test.")
    parser.add_argument("--sensitive-option", action="append", default=[], metavar="FLAG",
                        help="Additional secret-valued option; repeat as --sensitive-option=--custom-flag.")
    parser.add_argument(
        "--fail-on",
        choices=["none", "warning", "high", "critical"],
        default="none",
        help="Exit non-zero if any issue at or above this severity exists.",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.max_capture < 0:
        raise ProbeInputError("INVALID_USAGE", "--timeout must be positive and --max-capture must be nonnegative.")
    try:
        base_cmd = shlex.split(args.cmd)
    except ValueError as exc:
        raise ProbeInputError("INVALID_COMMAND", "--cmd must contain a valid shell-quoted argument list.") from exc
    if not all(valid_text(part) for part in base_cmd):
        raise ProbeInputError("INVALID_COMMAND", "--cmd arguments must be NUL-free UTF-8 strings.")
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
    if any(not isinstance(test, dict) or test.get("effects") not in ("read-only", "mutating") for test in tests):
        envelope = result_envelope("error", data={}, error={
            "code": "SAFETY_CLASSIFICATION_REQUIRED",
            "message": "Every test must declare effects as read-only or mutating before any command can run.",
            "details": {},
            "recoverable": True,
            "suggested_actions": ["Classify unknown, plan/dry-run, and negative mutation tests as mutating."],
        })
        print(json.dumps(envelope, indent=2))
        return 2
    if any(test["effects"] == "mutating" for test in tests) and not (
        args.allow_mutations and args.isolated_environment and args.isolated_environment.strip()
    ):
        envelope = result_envelope("error", data={}, error={
            "code": "UNSAFE_OPERATION",
            "message": "Mutating probes require --allow-mutations and --isolated-environment.",
            "details": {},
            "recoverable": True,
            "suggested_actions": ["Provision disposable resources with test-only credentials/configuration before opting in."],
        })
        print(json.dumps(envelope, indent=2))
        return 6
    secrets: set[str] = set()
    collect_secrets(dict(os.environ), secrets)
    collect_argument_secrets(base_cmd, secrets, args.sensitive_option)
    for test in tests:
        if isinstance(test, dict):
            collect_secrets(test.get("env", {}), secrets)
            arguments = test.get("args", [])
            if isinstance(arguments, list) and all(isinstance(item, str) for item in arguments):
                collect_argument_secrets(base_cmd + arguments, secrets, args.sensitive_option)
    try:
        results = [run_one(base_cmd, test, args.timeout, args.max_capture, secrets) for test in tests]
    except (ProcessInterrupted, ContainmentError) as exc:
        interrupted = isinstance(exc, ProcessInterrupted)
        envelope = result_envelope("error", data={}, error={
            "code": "INTERRUPTED" if interrupted else "CONTAINMENT_FAILED",
            "message": "Probe interrupted; owned processes were stopped." if interrupted else str(exc),
            "details": {},
            "recoverable": False,
            "suggested_actions": ["Inspect the execution environment before retrying."],
        })
        print(json.dumps(envelope, indent=2))
        return 128 + exc.signum if interrupted else 13
    summary = summarize(results)
    status = "success" if summary["tests_failed"] == 0 else "partial"
    data = {
        "base_command": base_cmd,
        "matrix": args.matrix or "<built-in>",
        "summary": summary,
        "results": results,
    }
    envelope = result_envelope(status, data=data)
    output = json.dumps(redact_data(envelope, secrets), indent=2, sort_keys=False)
    if args.out:
        try:
            Path(args.out).write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            raise ProbeInputError("REPORT_WRITE_FAILED", "Could not write the probe report.",
                                  {"error_type": type(exc).__name__}, exit_code=3) from exc
    else:
        print(output)

    if args.fail_on != "none":
        threshold = SEVERITY_ORDER[args.fail_on]
        for result in results:
            for item in result.get("issues") or []:
                if SEVERITY_ORDER.get(item.get("severity", "info"), 0) >= threshold:
                    return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    try:
        return probe_main(argv)
    except ProbeInputError as exc:
        error = {"code": exc.code, "message": str(exc), "details": exc.details,
                 "recoverable": True, "suggested_actions": ["Correct the input or path and retry."]}
        exit_code = exc.exit_code
    except Exception as exc:  # noqa: BLE001 - preserve the public JSON protocol
        error = {"code": "INTERNAL_ERROR", "message": "The probe failed unexpectedly.",
                 "details": {"error_type": type(exc).__name__}, "recoverable": False,
                 "suggested_actions": ["Report this failure without retrying unchanged input."]}
        exit_code = 13
    print(json.dumps(result_envelope("error", data={}, error=error), indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
