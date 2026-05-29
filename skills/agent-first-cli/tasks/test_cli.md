# Task: Test an Agent-First CLI

Use this playbook to build contract, regression, and safety tests for an agent-first CLI.

## Test layers

Use three layers:

1. Static catalog linting.
2. Dynamic CLI probes.
3. Project-specific integration tests.

## Layer 1: Static catalog linting

Create a command catalog using `templates/command_catalog.template.json`.

Run:

```bash
python scripts/afcli_schema_lint.py path/to/command_catalog.json
```

Static checks catch missing descriptions, weak mutation safety, missing global flags, and incomplete error taxonomy.

## Layer 2: Dynamic CLI probes

Create a matrix file. Start from `examples/probe_matrix.example.json`.

Run:

```bash
python scripts/afcli_probe.py --cmd "tool" --matrix path/to/probe_matrix.json --out probe-report.json
```

The probe checks:

- Exit codes.
- JSON parseability.
- Envelope fields.
- Error codes.
- ANSI/color pollution in standard output.
- Timeouts and possible interactive prompts.

## Probe matrix format

```json
{
  "tests": [
    {
      "name": "version_json",
      "args": ["version", "--output", "json"],
      "expect_exit": [0],
      "expect_json_stdout": true,
      "expect_status": ["success"],
      "timeout_seconds": 10
    }
  ]
}
```

Fields:

| Field | Meaning |
|---|---|
| `name` | Stable test name |
| `args` | Arguments appended to the base command |
| `stdin` | Optional string passed to standard input |
| `expect_exit` | List of acceptable exit codes |
| `expect_json_stdout` | Whether standard output must parse as JSON |
| `expect_status` | Acceptable top-level JSON `status` values |
| `expect_error_code` | Acceptable `error.code` values |
| `timeout_seconds` | Per-test timeout |

## Required test cases

Every CLI should have tests for:

```text
version_json
capabilities_json
commands_json
help_text
bad_flag_json_error
missing_required_option_json_error
invalid_enum_json_error
not_found_json_error
config_effective_json
doctor_json
```

Every mutating command should have:

```text
mutation_plan_json
mutation_apply_without_confirm_blocked
mutation_apply_with_confirm_json
mutation_idempotency_retry
```

Every destructive command should have:

```text
destructive_apply_requires_exact_confirmation
destructive_plan_reports_blast_radius
destructive_apply_reports_operation_id
destructive_apply_reports_rollback_support
```

Every list command should have:

```text
list_limit_json
list_cursor_json
list_fields_json
list_filter_json
```

Every long-running command should have:

```text
job_start_returns_id
job_status_json
job_cancel_plan_or_apply
job_timeout_json_error
```

## Assertions for JSON mode

For any command using `--output json`, assert:

- Standard output is valid JSON.
- Standard output contains no ANSI escape codes.
- Standard output contains one JSON document, not mixed logs.
- `status` exists.
- `command` exists.
- `metadata.schema_version` exists.
- `error.code` exists when `status` is `error`.
- `warnings` is an array when present.
- Secrets are redacted.

## Assertions for non-interactive mode

For any command using `--agent` or `--no-input`, assert:

- The command never waits indefinitely.
- It exits with a structured error if required input is missing.
- It does not ask the user to choose from an interactive menu.
- It does not prompt for credentials.

## Assertions for mutating commands

For mutation safety, assert:

- Plan mode does not mutate external state.
- Apply mode without confirmation fails closed.
- Destructive apply requires exact confirmation.
- Plan output describes changes.
- Apply output includes operation ID or resource ID.
- Retry with the same idempotency key does not duplicate effects.

## Continuous integration gate

A good continuous integration gate:

```bash
python scripts/afcli_schema_lint.py command_catalog.json --fail-on warning
python scripts/afcli_probe.py --cmd "tool" --matrix probe_matrix.json --fail-on critical
```

For stricter projects, fail on warnings as well.

## Regression strategy

Preserve sample JSON outputs as golden files. Compare shape, not volatile values.

Stable fields:

- `status`
- `command`
- top-level `data` keys
- `error.code`
- `metadata.schema_version`

Volatile fields to normalize:

- timestamps
- duration
- trace IDs
- operation IDs
- random IDs
- absolute paths

## Final test report format

Use this structure:

```text
Test scope:
Commands tested:
Static lint result:
Dynamic probe result:
Critical failures:
Warnings:
Safety failures:
Compatibility concerns:
Recommended fixes:
```
