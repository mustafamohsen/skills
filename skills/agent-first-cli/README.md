# Agent-First CLI Skill

This package is a reusable AI-agent skill for designing, implementing, auditing, and testing command-line applications that are primarily consumed by AI agents.

The package follows progressive disclosure:

- `SKILL.md` is intentionally compact and should be loaded first.
- `tasks/` contains workflow-specific playbooks.
- `docs/` contains deeper reference material.
- `templates/` contains machine-readable schema starting points.
- `scripts/` contains small JSON-emitting tools for static linting and live CLI probes.
- `examples/` contains runnable sample inputs for the scripts.

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
