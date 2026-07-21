#!/usr/bin/env python3
"""Lint an agent-first CLI command catalog.

The linter is intentionally lightweight: it uses only the Python standard
library and emits a JSON result envelope suitable for AI-agent consumption.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SEVERITY_ORDER = {"info": 0, "low": 1, "warning": 2, "high": 3, "critical": 4}
CORE_ERROR_CODES = {
    "INVALID_USAGE",
    "VALIDATION_FAILED",
    "CONFIGURATION_ERROR",
    "AUTHENTICATION_REQUIRED",
    "PERMISSION_DENIED",
    "RESOURCE_NOT_FOUND",
    "AMBIGUOUS_RESOURCE",
    "CONFLICT",
    "UNSAFE_OPERATION",
    "NETWORK_ERROR",
    "TIMEOUT",
    "RATE_LIMITED",
    "PARTIAL_FAILURE",
    "UNSUPPORTED_OPERATION",
    "INTERNAL_ERROR",
}
DISCOVERY_COMMANDS = {"version", "capabilities", "commands", "doctor"}


def normalize_name(name: Any) -> str:
    return str(name or "").strip().lstrip("-").replace("_", "-").lower()


def option_names(options: Iterable[Dict[str, Any]]) -> set[str]:
    return {normalize_name(opt.get("name")) for opt in options if isinstance(opt, dict)}


def find_option(options: Iterable[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    target = normalize_name(name)
    for opt in options:
        if isinstance(opt, dict) and normalize_name(opt.get("name")) == target:
            return opt
    return None


def structure_error(errors: List[Dict[str, str]], path: str, expected: str, value: Any) -> None:
    errors.append(
        {
            "path": path,
            "issue": f"Expected {expected}.",
            "actual_type": type(value).__name__,
        }
    )


def validate_string_list(value: Any, path: str, errors: List[Dict[str, str]]) -> None:
    if not isinstance(value, list):
        structure_error(errors, path, "an array", value)
        return
    for index, item in enumerate(value):
        if not isinstance(item, str):
            structure_error(errors, f"{path}[{index}]", "a string", item)


def validate_options(value: Any, path: str, errors: List[Dict[str, str]]) -> None:
    if not isinstance(value, list):
        structure_error(errors, path, "an array", value)
        return
    for index, option in enumerate(value):
        option_path = f"{path}[{index}]"
        if not isinstance(option, dict):
            structure_error(errors, option_path, "an object", option)
            continue
        for key in ("name", "type", "description"):
            if key in option and not isinstance(option[key], str):
                structure_error(errors, f"{option_path}.{key}", "a string", option[key])
        for key in ("required", "sensitive"):
            if key in option and not isinstance(option[key], bool):
                structure_error(errors, f"{option_path}.{key}", "a boolean", option[key])
        if "values" in option:
            validate_string_list(option["values"], f"{option_path}.values", errors)


def validate_catalog_structure(catalog: Any) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    if not isinstance(catalog, dict):
        structure_error(errors, "$", "an object", catalog)
        return errors

    for key in ("tool", "description", "schema_version"):
        if key in catalog and not isinstance(catalog[key], str):
            structure_error(errors, f"$.{key}", "a string", catalog[key])
    for key in ("output_formats", "error_codes"):
        if key in catalog:
            validate_string_list(catalog[key], f"$.{key}", errors)
    if "global_options" in catalog:
        validate_options(catalog["global_options"], "$.global_options", errors)

    if "commands" in catalog:
        commands = catalog["commands"]
        if not isinstance(commands, list):
            structure_error(errors, "$.commands", "an array", commands)
        else:
            for index, command in enumerate(commands):
                command_path = f"$.commands[{index}]"
                if not isinstance(command, dict):
                    structure_error(errors, command_path, "an object", command)
                    continue
                for key in ("name", "shell", "description"):
                    if key in command and not isinstance(command[key], str):
                        structure_error(errors, f"{command_path}.{key}", "a string", command[key])
                for key in (
                    "reads_state",
                    "mutates_state",
                    "destructive",
                    "long_running",
                    "large_output",
                    "requires_auth",
                ):
                    if key in command and not isinstance(command[key], bool):
                        structure_error(errors, f"{command_path}.{key}", "a boolean", command[key])
                if "options" in command:
                    validate_options(command["options"], f"{command_path}.options", errors)
                for key in ("output_formats", "error_codes"):
                    if key in command:
                        validate_string_list(command[key], f"{command_path}.{key}", errors)
                boolean_metadata = {
                    "safety": (
                        "supports_plan",
                        "supports_dry_run",
                        "requires_confirmation",
                        "supports_idempotency_key",
                        "reports_blast_radius",
                        "reports_rollback",
                    ),
                    "pagination": (
                        "supports_limit",
                        "supports_cursor",
                        "supports_filter",
                        "supports_fields",
                    ),
                }
                for key, boolean_fields in boolean_metadata.items():
                    if key not in command:
                        continue
                    value = command[key]
                    if not isinstance(value, dict):
                        structure_error(errors, f"{command_path}.{key}", "an object", value)
                        continue
                    for field in boolean_fields:
                        if field in value and not isinstance(value[field], bool):
                            structure_error(errors, f"{command_path}.{key}.{field}", "a boolean", value[field])
    return errors


def issue(
    issues: List[Dict[str, Any]],
    severity: str,
    area: str,
    message: str,
    command: Optional[str] = None,
    recommendation: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    item: Dict[str, Any] = {
        "severity": severity,
        "area": area,
        "message": message,
    }
    if command:
        item["command"] = command
    if recommendation:
        item["recommendation"] = recommendation
    if details:
        item["details"] = details
    issues.append(item)


def command_output_formats(catalog: Dict[str, Any], command: Dict[str, Any]) -> set[str]:
    values = command.get("output_formats") or catalog.get("output_formats") or []
    return {str(v).lower() for v in values}


def has_mode_plan_apply(command: Dict[str, Any]) -> bool:
    mode = find_option(command.get("options") or [], "mode")
    if not mode:
        return False
    values = {str(v).lower() for v in mode.get("values") or []}
    return {"plan", "apply"}.issubset(values)


def lint_catalog(catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []

    if not catalog.get("tool"):
        issue(issues, "critical", "catalog", "Missing required `tool` name.")

    commands = catalog.get("commands")
    if not isinstance(commands, list) or not commands:
        issue(issues, "critical", "catalog", "Catalog must include a non-empty `commands` array.")
        commands = []

    output_formats = {str(v).lower() for v in catalog.get("output_formats") or []}
    if "json" not in output_formats:
        issue(
            issues,
            "critical",
            "output",
            "Catalog-level output formats do not include `json`.",
            recommendation="Add `json` as a supported output format and document the JSON envelope.",
        )

    globals_ = catalog.get("global_options") or []
    if not isinstance(globals_, list):
        issue(issues, "critical", "global_options", "`global_options` must be an array.")
        globals_ = []
    global_names = option_names(globals_)

    if "output" not in global_names:
        issue(issues, "critical", "global_options", "Missing global `--output` option.")
    else:
        output_opt = find_option(globals_, "output") or {}
        values = {str(v).lower() for v in output_opt.get("values") or []}
        if output_opt.get("type") == "enum" and "json" not in values:
            issue(issues, "critical", "global_options", "Global `--output` enum does not include `json`.")

    if "agent" not in global_names and "no-input" not in global_names:
        issue(
            issues,
            "high",
            "global_options",
            "Missing `--agent` or `--no-input` global option.",
            recommendation="Add a non-interactive mode that fails instead of prompting.",
        )
    if "no-color" not in global_names:
        issue(issues, "warning", "global_options", "Missing `--no-color` global option.")
    if "timeout" not in global_names:
        issue(issues, "warning", "global_options", "Missing `--timeout` global option.")
    if "log-level" not in global_names:
        issue(issues, "low", "global_options", "Consider adding `--log-level` for diagnostics.")
    if "trace-id" not in global_names:
        issue(issues, "low", "global_options", "Consider adding `--trace-id` for correlation.")

    error_codes = {str(v) for v in catalog.get("error_codes") or []}
    if not error_codes:
        issue(issues, "high", "errors", "Catalog does not define stable error codes.")
    else:
        missing_core = sorted(CORE_ERROR_CODES - error_codes)
        if missing_core:
            issue(
                issues,
                "warning",
                "errors",
                "Catalog is missing some recommended core error codes.",
                details={"missing_error_codes": missing_core},
            )

    seen: set[str] = set()
    for cmd in commands:
        if not isinstance(cmd, dict):
            issue(issues, "critical", "commands", "Each command entry must be an object.")
            continue
        name = str(cmd.get("name") or "").strip()
        if not name:
            issue(issues, "critical", "commands", "A command is missing `name`.")
            continue
        if name in seen:
            issue(issues, "critical", "commands", f"Duplicate command name `{name}`.", command=name)
        seen.add(name)

        if "." not in name and name not in DISCOVERY_COMMANDS:
            issue(
                issues,
                "warning",
                "commands",
                "Command name is not in stable dotted form `resource.action`.",
                command=name,
            )
        if not str(cmd.get("description") or "").strip():
            issue(issues, "high", "commands", "Command is missing a description.", command=name)

        formats = command_output_formats(catalog, cmd)
        if "json" not in formats:
            issue(
                issues,
                "high",
                "output",
                "Command does not advertise JSON output.",
                command=name,
            )

        opts = cmd.get("options") or []
        if not isinstance(opts, list):
            issue(issues, "critical", "options", "Command `options` must be an array.", command=name)
            opts = []
        names = option_names(opts)
        for opt in opts:
            if not isinstance(opt, dict):
                issue(issues, "critical", "options", "Each option must be an object.", command=name)
                continue
            opt_name = normalize_name(opt.get("name"))
            if not opt_name:
                issue(issues, "critical", "options", "Option is missing `name`.", command=name)
            if not opt.get("type"):
                issue(issues, "high", "options", f"Option `{opt_name}` is missing `type`.", command=name)
            if opt.get("type") == "enum" and not opt.get("values"):
                issue(issues, "high", "options", f"Enum option `{opt_name}` is missing `values`.", command=name)
            if opt_name.startswith("no-no-"):
                issue(issues, "warning", "options", f"Option `{opt_name}` has confusing double negative naming.", command=name)

        cmd_error_codes = cmd.get("error_codes") or []
        if not cmd_error_codes:
            issue(issues, "warning", "errors", "Command does not list possible error codes.", command=name)

        mutates = bool(cmd.get("mutates_state"))
        destructive = bool(cmd.get("destructive"))
        safety = cmd.get("safety") or {}
        if mutates:
            supports_plan = bool(safety.get("supports_plan")) or has_mode_plan_apply(cmd)
            supports_dry_run = bool(safety.get("supports_dry_run")) or "dry-run" in names
            if not (supports_plan or supports_dry_run):
                issue(
                    issues,
                    "critical",
                    "mutation_safety",
                    "Mutating command lacks plan/apply or dry-run support.",
                    command=name,
                    recommendation="Add `--mode plan|apply` or `--dry-run` and document side-effect behavior.",
                )
            supports_idempotency = bool(safety.get("supports_idempotency_key")) or "idempotency-key" in names
            if not supports_idempotency:
                issue(
                    issues,
                    "warning",
                    "mutation_safety",
                    "Mutating command does not advertise idempotency-key support.",
                    command=name,
                )
        if destructive:
            requires_confirmation = bool(safety.get("requires_confirmation")) or "confirm" in names
            if not requires_confirmation:
                issue(
                    issues,
                    "critical",
                    "mutation_safety",
                    "Destructive command does not require explicit confirmation.",
                    command=name,
                    recommendation="Require `--confirm <resource-id-or-token>` for apply mode.",
                )
            if not safety.get("reports_blast_radius"):
                issue(issues, "warning", "mutation_safety", "Destructive command should report blast radius in plan output.", command=name)
            if not safety.get("reports_rollback"):
                issue(issues, "warning", "mutation_safety", "Destructive command should report rollback support or lack of support.", command=name)

        if bool(cmd.get("large_output")):
            pagination = cmd.get("pagination") or {}
            supports_limit = bool(pagination.get("supports_limit")) or "limit" in names
            supports_cursor = bool(pagination.get("supports_cursor")) or "cursor" in names
            if not supports_limit:
                issue(issues, "high", "pagination", "Large-output command lacks `--limit` support.", command=name)
            if not supports_cursor:
                issue(issues, "warning", "pagination", "Large-output command should support cursor pagination.", command=name)
            if "fields" not in names and not pagination.get("supports_fields"):
                issue(issues, "low", "pagination", "Consider field selection for large-output command.", command=name)

        if bool(cmd.get("long_running")):
            if not (cmd.get("returns_operation_id") or cmd.get("returns_job_id") or cmd.get("returns_status_command")):
                issue(
                    issues,
                    "high",
                    "long_running",
                    "Long-running command should declare that it returns an operation/job ID or status command.",
                    command=name,
                )

    missing_discovery = sorted(DISCOVERY_COMMANDS - seen)
    if missing_discovery:
        issue(
            issues,
            "warning",
            "discovery",
            "Catalog is missing recommended discovery commands.",
            details={"missing_commands": missing_discovery},
        )

    return issues


def summarize(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {sev: 0 for sev in SEVERITY_ORDER}
    for item in issues:
        sev = item.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    worst = "none"
    for sev, rank in SEVERITY_ORDER.items():
        if counts.get(sev, 0) and (worst == "none" or rank > SEVERITY_ORDER[worst]):
            worst = sev
    return {
        "issue_count": len(issues),
        "counts_by_severity": counts,
        "worst_severity": worst,
    }


def result_envelope(status: str, data: Dict[str, Any], error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "status": status,
        "command": "afcli.schema_lint",
        "data": data,
        "warnings": [],
        "error": error,
        "metadata": {
            "tool_version": "1.0.0",
            "schema_version": "1.0",
        },
    }


def process_catalog(catalog: Any, catalog_path: str, output_path: Optional[str], fail_on: str) -> int:
    structure_errors = validate_catalog_structure(catalog)
    if structure_errors:
        envelope = result_envelope(
            "error",
            data={"catalog": catalog_path},
            error={
                "code": "CATALOG_INVALID",
                "message": "Catalog structure is invalid.",
                "details": {
                    "catalog": catalog_path,
                    "errors": structure_errors,
                },
                "recoverable": True,
                "suggested_actions": ["Fix the reported catalog structure and run the linter again."],
            },
        )
        print(json.dumps(envelope, indent=2, sort_keys=False))
        return 2

    issues = lint_catalog(catalog)
    data = {
        "catalog": catalog_path,
        "summary": summarize(issues),
        "issues": issues,
    }
    status = "success" if not issues else "partial"
    envelope = result_envelope(status, data=data)
    output = json.dumps(envelope, indent=2, sort_keys=False)
    if output_path:
        Path(output_path).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    if fail_on != "none":
        threshold = SEVERITY_ORDER[fail_on]
        if any(SEVERITY_ORDER.get(i.get("severity", "info"), 0) >= threshold for i in issues):
            return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Lint an agent-first CLI command catalog and emit a JSON report.")
    parser.add_argument("catalog", help="Path to command catalog JSON.")
    parser.add_argument("--out", help="Optional path to write report JSON. Defaults to stdout.")
    parser.add_argument(
        "--fail-on",
        choices=["none", "warning", "high", "critical"],
        default="none",
        help="Exit non-zero if any issue at or above this severity exists.",
    )
    args = parser.parse_args(argv)

    try:
        text = Path(args.catalog).read_text(encoding="utf-8")
        catalog = json.loads(text)
    except Exception as exc:  # noqa: BLE001 - report as structured JSON
        envelope = result_envelope(
            "error",
            data={"catalog": args.catalog},
            error={
                "code": "CATALOG_READ_FAILED",
                "message": str(exc),
                "details": {"catalog": args.catalog},
                "recoverable": True,
                "suggested_actions": ["Check that the catalog path exists and contains valid JSON."],
            },
        )
        print(json.dumps(envelope, indent=2, sort_keys=False))
        return 2

    try:
        return process_catalog(catalog, args.catalog, args.out, args.fail_on)
    except Exception as exc:  # noqa: BLE001 - preserve the JSON protocol on unexpected faults
        envelope = result_envelope(
            "error",
            data={"catalog": args.catalog},
            error={
                "code": "INTERNAL_ERROR",
                "message": "The catalog validator failed unexpectedly.",
                "details": {
                    "catalog": args.catalog,
                    "error_type": type(exc).__name__,
                },
                "recoverable": False,
                "suggested_actions": ["Report the validator failure without retrying unchanged input."],
            },
        )
        print(json.dumps(envelope, indent=2, sort_keys=False))
        return 13


if __name__ == "__main__":
    raise SystemExit(main())
