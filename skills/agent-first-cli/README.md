# Agent-First CLI Skill

This package is a reusable AI-agent skill for designing, implementing, auditing, and testing command-line applications that are primarily consumed by AI agents.

The package follows progressive disclosure:

- `SKILL.md` is intentionally compact and should be loaded first.
- `tasks/` contains workflow-specific playbooks.
- `docs/` contains deeper reference material.
- `templates/` contains machine-readable schema starting points.
- `scripts/` contains small JSON-emitting tools for static linting and live CLI probes.
- `examples/` contains runnable sample inputs for the scripts.
- `tests/` contains zero-install black-box regression tests for the public scripts.

## Package layout

```text
agent-first-cli-skill/
  SKILL.md
  README.md
  manifest.txt
  docs/
    agent_first_contract.md
    output_and_errors.md
    safety_and_mutation.md
    versioning_and_compatibility.md
  tasks/
    design_cli.md
    audit_existing_cli.md
    implement_command.md
    test_cli.md
    write_docs.md
  templates/
    command_catalog.schema.json
    result_envelope.schema.json
    error_envelope.schema.json
    command_catalog.template.json
  examples/
    command_catalog.example.json
    probe_matrix.example.json
  scripts/
    afcli_probe.py
    afcli_schema_lint.py
  tests/
    test_afcli_schema_lint.py
    test_probe_input_errors.py
```

## Typical uses

### Designing a new CLI

1. Load `SKILL.md`.
2. Load `tasks/design_cli.md`.
3. Use `templates/command_catalog.template.json` to draft the command catalog.
4. Use `scripts/afcli_schema_lint.py` to check the catalog.

### Auditing an existing CLI

1. Load `SKILL.md`.
2. Load `tasks/audit_existing_cli.md`.
3. Build a probe matrix from the CLI's help output.
4. Run `scripts/afcli_probe.py`.
5. Summarize gaps by severity.

### Implementing one command

1. Load `SKILL.md`.
2. Load `tasks/implement_command.md`.
3. Check output and error shapes against `docs/output_and_errors.md`.
4. Add contract tests from `tasks/test_cli.md`.

## Script examples

```bash
python scripts/afcli_schema_lint.py examples/command_catalog.example.json
python scripts/afcli_probe.py --cmd "python -m mytool" --matrix examples/probe_matrix.example.json --out probe-report.json
```

The scripts use only the Python standard library.

## Probe input and failure protocol

The probe validates the whole custom matrix before executing any test. `tests` must be a non-empty array of objects; args/environment values/stdin must have the documented string types, timeouts must be positive integers, and expectation lists must be non-empty with correctly typed entries. Unknown extension fields remain allowed. See `tasks/test_cli.md` for field types.

Malformed CLI output (including invalid UTF-8, non-finite JSON numbers, and wrongly typed envelope fields) becomes a per-test finding; subsequent tests still run. Execution failures such as permission errors also become critical per-test findings. `--fail-on` continues to determine the report's exit status.

Fatal input/reporting errors always emit one JSON envelope on stdout, even when `--out` was requested:

| Code | Exit | Meaning |
|---|---:|---|
| `INVALID_USAGE` / `INVALID_COMMAND` | 2 | Invalid flags, bounds, or command quoting |
| `MATRIX_READ_FAILED` | 2 | Unreadable file or invalid JSON |
| `MATRIX_INVALID` | 2 | Invalid matrix shape; `details.path` identifies the field |
| `REPORT_WRITE_FAILED` | 3 | Report destination could not be written |
| `INTERNAL_ERROR` | 13 | Unexpected probe fault; no traceback or raw exception values are emitted |

`--help` remains ordinary argparse help text. Correctly formed reports still honor `--out` without stdout output.

## Verification

From the repository root:

```bash
python3 -m unittest discover -s skills/agent-first-cli/tests -p 'test_*.py'
```
