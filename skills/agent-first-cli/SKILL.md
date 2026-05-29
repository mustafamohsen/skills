---
name: agent-first-cli
description: Design, implement, audit, and test command-line interfaces intended to be consumed primarily by AI agents. Use for agent-safe CLI contracts, machine-readable output, non-interactive execution, error taxonomies, safety gates for mutating commands, schema introspection, help/documentation design, and regression probes. Start here, then open only the task-specific file needed.
---

# Agent-First CLI Skill

Use this skill when working on a command-line interface (CLI) that should be reliable for AI agents, automation, and scripted consumers.

The operating principle is: **treat the CLI as a stable protocol over the shell, not as an interactive human interface.**

## Start with the smallest useful path

Do not load every file in this package. Choose one path:

| Task | Open next |
|---|---|
| Design a new agent-first CLI | `tasks/design_cli.md` |
| Audit an existing CLI | `tasks/audit_existing_cli.md` |
| Implement or review one command | `tasks/implement_command.md` |
| Build contract/regression tests | `tasks/test_cli.md` |
| Write CLI help, docs, or examples | `tasks/write_docs.md` |
| Need the full recommended contract | `docs/agent_first_contract.md` |
| Need mutation safety rules | `docs/safety_and_mutation.md` |
| Need output/error schema details | `docs/output_and_errors.md` |
| Need release compatibility rules | `docs/versioning_and_compatibility.md` |

## Non-negotiable agent-first criteria

A CLI is not agent-first unless it can satisfy these baseline checks:

1. Every command can run non-interactively.
2. Machine-readable output is available for success, warning, partial, and error cases.
3. Standard output is reserved for the primary result; diagnostics go to standard error.
4. Errors include stable machine-readable codes.
5. Mutating commands have a safe preview path: `--mode plan`, `--dry-run`, or equivalent.
6. Destructive commands require explicit confirmation, preferably a resource ID or confirmation token.
7. Long-running commands return job or operation identifiers.
8. Large result sets are paginated or streamable.
9. Capabilities, version, schemas, and effective configuration are discoverable.
10. JSON contracts are versioned and backwards-compatible within a major version.

## Preferred global flags

Recommend these unless the host project has a strong reason to use different names:

```bash
--output <json|jsonl|text|yaml>
--agent
--no-input
--no-color
--quiet
--verbose
--debug
--log-level <error|warn|info|debug|trace>
--log-file <path>
--config <path>
--profile <name>
--cwd <path>
--timeout <duration>
--trace-id <id>
```

For mutating commands:

```bash
--mode <plan|apply>
--dry-run
--confirm <token-or-resource-id>
--force
--idempotency-key <key>
```

For list commands:

```bash
--limit <number>
--cursor <token>
--filter <expression>
--sort <field>
--fields <field1,field2>
```

## Standard JSON envelope

Use this minimal shape unless a project-specific schema already exists:

```json
{
  "status": "success | error | partial",
  "command": "resource.action",
  "data": {},
  "warnings": [],
  "error": null,
  "metadata": {
    "tool_version": "string",
    "schema_version": "string",
    "duration_ms": 0
  }
}
```

Error shape:

```json
{
  "status": "error",
  "command": "resource.action",
  "error": {
    "code": "STABLE_ERROR_CODE",
    "message": "Human-readable message",
    "details": {},
    "recoverable": true,
    "suggested_actions": []
  },
  "metadata": {
    "tool_version": "string",
    "schema_version": "string"
  }
}
```

## Included scripts

Use scripts only when they advance the current task.

```bash
# Probe a live CLI against a small matrix of commands.
python scripts/afcli_probe.py --cmd "mytool" --matrix examples/probe_matrix.example.json

# Lint a command catalog/specification.
python scripts/afcli_schema_lint.py examples/command_catalog.example.json
```

Both scripts emit JSON reports so an agent can parse and summarize results.

## Shipping discipline

Before calling a CLI agent-first, verify it with:

1. Static contract review using a command catalog or schema.
2. Dynamic probe of successful, invalid, missing-auth, missing-argument, and destructive-operation cases.
3. Documentation review for examples, global flags, exit codes, output schemas, and safety semantics.
4. Backwards-compatibility review for any schema, flag, command, or error-code changes.

Keep context focused: load the narrow task guide first, then load reference docs only when the task requires deeper detail.
