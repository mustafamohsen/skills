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
    test_probe_mutation_safety.py
    test_probe_redaction.py
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

Probe matrices must classify every test with `effects: "read-only"` or `effects: "mutating"`. Existing custom matrices need this field. Mutating matrices are blocked unless both `--allow-mutations` and `--isolated-environment <description>` are supplied. Follow `tasks/audit_existing_cli.md` to provision disposable resources and test-only credentials/configuration first. These flags attest to an already isolated environment; the probe is not a sandbox.

## Probe report privacy

Probe reports redact nested JSON credential fields, common credential text/header forms, private-key blocks, and secret-valued arguments (`--token value` or `--token=value`). Values learned from sensitive environment variables, matrix environment overrides, arguments, and captured JSON are removed throughout the report, including names, issue details, and command metadata. Redaction precedes preview truncation and applies to stdout and `--out` reports without changing the command executed.

Register nonstandard credential flags with repeatable `--sensitive-option=--login` (or `--sensitive-option=-p`). Redaction is best-effort for arbitrary text: unnamed positional credentials, custom field names, encoded values, and unknown log formats cannot reliably be identified. Avoid placing secrets there and inspect reports before sharing; use `--max-capture 0` when output previews are inappropriate.

## Verification

From the repository root:

```bash
python3 -m unittest discover -s skills/agent-first-cli/tests -p 'test_*.py'
```
