# Agent-First CLI Contract

This document defines the recommended contract for a command-line interface whose primary consumer is an AI agent or automation system.

## Design goal

An agent-first CLI should let a capable but literal AI agent:

1. Discover what the tool can do.
2. Supply complete inputs without interactive clarification.
3. Execute safely.
4. Parse success, partial success, warnings, and errors.
5. Recover or retry without guessing.
6. Avoid damaging operations unless explicitly authorized.

## Command shape

Prefer a predictable resource/action hierarchy:

```bash
tool <resource> <action> [options]
```

Examples:

```bash
tool project list --output json
tool project get --id prj_123 --output json
tool project create --name booksqa --mode plan --output json
tool project delete --id prj_123 --mode apply --confirm prj_123 --output json
```

Recommended command names in machine metadata should use a stable dotted form:

```text
project.list
project.get
project.create
project.delete
```

## Discovery commands

An agent-first CLI should expose its own surface area.

Recommended minimum:

```bash
tool version --output json
tool capabilities --output json
tool commands --output json
tool command-schema <command> --output json
tool config effective --output json
tool doctor --output json
```

`tool capabilities --output json` should answer these questions:

- Which commands exist?
- Which output formats are supported?
- Are dry-run or plan/apply modes supported?
- Does the CLI support non-interactive execution?
- Which schema version is active?
- Which features are experimental or deprecated?

## Global options

Recommended global options:

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

`--agent` may be a convenience flag equivalent to:

```bash
--output json --no-input --no-color --log-level warn
```

Do not make `--agent` hide safety behavior. It should make the command more parseable, not more permissive.

## Output channels

Use channels consistently:

| Channel | Purpose |
|---|---|
| Standard output | Primary result, especially JSON/JSON Lines |
| Standard error | Logs, diagnostics, progress, warnings for humans |
| Exit code | Coarse outcome class |
| Optional log file | Debug or trace details |

When `--output json` is used, standard output should contain one complete JSON document. When `--output jsonl` is used, each line should be a valid JSON object.

## Standard result envelope

Success:

```json
{
  "status": "success",
  "command": "project.get",
  "data": {
    "id": "prj_123",
    "name": "booksqa"
  },
  "warnings": [],
  "error": null,
  "metadata": {
    "tool_version": "1.4.2",
    "schema_version": "1.0",
    "duration_ms": 38
  }
}
```

Partial success:

```json
{
  "status": "partial",
  "command": "batch.delete",
  "data": {
    "succeeded": 8,
    "failed": 2,
    "failed_items": [
      {"id": "item_7", "error_code": "PERMISSION_DENIED"},
      {"id": "item_9", "error_code": "NOT_FOUND"}
    ]
  },
  "warnings": [],
  "error": null,
  "metadata": {
    "tool_version": "1.4.2",
    "schema_version": "1.0",
    "duration_ms": 1120
  }
}
```

Error:

```json
{
  "status": "error",
  "command": "project.get",
  "data": null,
  "warnings": [],
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Project was not found.",
    "details": {
      "resource": "project",
      "id": "prj_missing"
    },
    "recoverable": true,
    "suggested_actions": [
      "Run `tool project list --output json` to inspect available projects."
    ]
  },
  "metadata": {
    "tool_version": "1.4.2",
    "schema_version": "1.0",
    "duration_ms": 21
  }
}
```

## Exit codes

Use documented, stable exit codes. A compact taxonomy is better than dozens of project-specific codes.

| Code | Meaning |
|---:|---|
| 0 | Success |
| 1 | General failure |
| 2 | Invalid usage or bad arguments |
| 3 | Configuration error |
| 4 | Authentication or authorization error |
| 5 | Resource not found |
| 6 | Conflict or unsafe operation |
| 7 | Network or external dependency failure |
| 8 | Validation failure |
| 9 | Partial failure |
| 10 | Timeout |
| 11 | Rate limited |
| 12 | Unsupported operation |
| 13 | Internal error |

The exit code gives the broad class. The JSON error code gives the precise machine-readable reason.

## Input modes

Support simple flags for simple commands:

```bash
tool task create --title "Review code" --priority high --output json
```

Support structured input for complex commands:

```bash
tool task create --input task.json --input-format json --output json
cat task.json | tool task create --input - --input-format json --output json
```

Recommended input flags:

```bash
--input <path|->
--input-format <json|yaml>
--validate-only
```

## Safety for mutations

For create, update, delete, deploy, migrate, grant, revoke, send, publish, or any other state-changing command, provide a safe preview.

Recommended pattern:

```bash
tool deploy --project booksqa --environment production --mode plan --output json
```

Then:

```bash
tool deploy \
  --project booksqa \
  --environment production \
  --mode apply \
  --confirm deploy:booksqa:production \
  --output json
```

The plan result should include:

- What will change.
- Whether the operation is destructive.
- Required permissions.
- Estimated cost, time, or blast radius if relevant.
- A confirmation token when appropriate.

## Long-running operations

Avoid keeping agents blocked indefinitely.

Prefer:

```bash
tool job start --input work.json --output json
tool job status --id job_123 --output json
tool job cancel --id job_123 --output json
```

A job-start response should include:

```json
{
  "status": "success",
  "command": "job.start",
  "data": {
    "job_id": "job_123",
    "state": "queued",
    "status_command": "tool job status --id job_123 --output json",
    "cancel_command": "tool job cancel --id job_123 --output json"
  }
}
```

## Pagination and streaming

Large outputs should not require reading unbounded data.

List commands should support:

```bash
--limit <number>
--cursor <token>
--filter <expression>
--sort <field>
--fields <field1,field2>
```

JSON pagination shape:

```json
{
  "status": "success",
  "command": "logs.list",
  "data": {
    "items": [],
    "pagination": {
      "limit": 100,
      "next_cursor": "cur_456",
      "has_more": true
    }
  }
}
```

For streaming, use JSON Lines:

```jsonl
{"type":"progress","current":1,"total":100}
{"type":"item","id":"item_1"}
{"type":"summary","processed":100,"failed":0}
```

## Configuration

Agents should be able to inspect the effective configuration before executing.

Recommended commands:

```bash
tool config validate --output json
tool config effective --output json
tool config explain --output json
```

The effective configuration should disclose loaded config files, selected profile, environment-derived values by source, and redacted secret presence.

## Documentation contract

Human help and machine introspection should agree.

At minimum, every command should document:

- Purpose.
- Required arguments/options.
- Defaults.
- Output formats.
- Exit codes.
- Error codes.
- Mutating/safety behavior.
- Examples for plan/apply, invalid input, and JSON output.

## Acceptance gate

Do not call a CLI agent-first until these are true:

- A non-interactive JSON path exists for each command.
- Error output is JSON when requested.
- Missing argument errors are field-specific.
- Mutating commands can be previewed.
- Destructive commands require explicit confirmation.
- Long jobs return IDs.
- Output contracts and error codes are documented.
- Contract tests run in continuous integration.
