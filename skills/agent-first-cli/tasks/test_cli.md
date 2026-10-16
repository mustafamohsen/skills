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

Create a matrix file. Start from `examples/probe_matrix.example.json`. Verify each test's `effects` classification against the actual CLI. Unknown behavior and negative mutation tests count as mutating, not read-only.

Before any mutation test (including plan/dry-run safety tests), provision disposable resources with test-only credentials, explicit endpoints/profile, isolated configuration and working directory, and no production access. Obtain authorization for test mutations. If this cannot be verified, skip execution and report the untested paths. The probe does not create a sandbox or strip ambient credentials.

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
      "effects": "read-only",
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
| `effects` | Required: `read-only` or `mutating`; classify conservatively |
| `args` | Array of NUL-free UTF-8 strings appended to the base command; defaults to `[]` |
| `stdin` | Optional UTF-8 string passed to standard input |
| `env` | Optional object of string values and nonempty names without NUL or `=` |
| `expect_exit` | Non-empty array of integer exit codes; booleans are not integers |
| `expect_json_stdout` | Boolean: stdout must parse as standard JSON |
| `expect_stderr_empty` | Boolean: stderr must be empty |
| `expect_status` | Non-empty array containing `success`, `partial`, or `error` |
| `expect_error_code` | Non-empty array of non-empty error-code strings |
| `timeout_seconds` | Positive integer seconds; defaults to `--timeout` |

Custom matrices require a non-empty `tests` array. The entire matrix is validated before any command runs, with invalid structure reported as JSON `MATRIX_INVALID` and a field path (exit 2). Malformed responses and execution failures are per-test findings, not reasons to discard the remaining tests. Fatal input/I/O errors use the protocol documented in `README.md`; `--help` is ordinary text. Unknown extension fields remain permitted.

A matrix containing any `mutating` test requires both `--allow-mutations` and a nonblank `--isolated-environment <description>`. These flags attest to verified isolation; they do not enforce it. Preflight rejects the whole matrix before any test starts if classification or authorization is missing.

```bash
# Run only from a verified disposable test environment.
python scripts/afcli_probe.py --cmd "tool" --matrix mutation_matrix.json \
  --allow-mutations --isolated-environment "local-disposable-fixtures" --fail-on critical
```

Existing custom matrices must add `effects` to every test. Gate errors are JSON on stdout: `SAFETY_CLASSIFICATION_REQUIRED` (exit 2) or `UNSAFE_OPERATION` (exit 6), regardless of `--fail-on` or `--out`.

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

For stricter projects, fail on warnings as well. The example gate above assumes a read-only matrix. Mutation CI jobs must provision the isolated environment first and pass both authorization flags; never reuse production credentials.

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
