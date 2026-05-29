# Task: Write Help, Reference Docs, and Examples

Use this playbook when writing documentation for an agent-first CLI.

## Documentation goal

Documentation should let both a human and an AI agent know:

1. What the command does.
2. What inputs are required.
3. What the command returns.
4. How errors are structured.
5. Whether the command mutates state.
6. How to preview, confirm, retry, paginate, or cancel.

## Help output structure

Every command should expose help similar to:

```text
Usage:
  tool project delete --id <project-id> --mode <plan|apply> [options]

Description:
  Deletes a project. In plan mode, returns the resources that would be deleted.
  In apply mode, requires explicit confirmation.

Required options:
  --id <project-id>        Stable project identifier.
  --mode <plan|apply>     Preview or execute the operation.

Safety options:
  --confirm <token>       Required for apply mode.
  --idempotency-key <key> Prevents duplicate external effects on retry.

Global options:
  --output <json|text>    Output format.
  --no-input              Fail instead of prompting.
  --no-color              Disable terminal color.
  --timeout <duration>    Maximum runtime.

Exit codes:
  0 success
  2 invalid usage
  5 resource not found
  6 unsafe operation

Examples:
  tool project delete --id prj_123 --mode plan --output json
  tool project delete --id prj_123 --mode apply --confirm prj_123 --output json
```

## Include JSON examples

For every major command, include at least one JSON success example and one JSON error example.

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
    "schema_version": "1.0"
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
      "id": "prj_missing"
    },
    "recoverable": true,
    "suggested_actions": [
      "Run `tool project list --output json`."
    ]
  }
}
```

## Machine-readable docs

Provide these commands where possible:

```bash
tool commands --output json
tool command-schema project.delete --output json
tool error-codes --output json
tool examples --output json
```

The machine-readable docs should match the human help text.

## Document safety plainly

For mutating commands, include:

```text
Mutation: yes
Destructive: yes/no
Preview support: --mode plan
Apply support: --mode apply
Confirmation required: yes/no
Idempotency support: yes/no
Rollback support: yes/no
```

Avoid hiding danger behind vague language like "cleanup" or "sync" when the command deletes, overwrites, sends, grants, revokes, or charges.

## Document defaults

Every default should be explicit.

Bad:

```text
Deploys the project.
```

Good:

```text
Deploys the project. No environment is selected by default. You must pass
`--environment dev`, `--environment staging`, or `--environment production`.
```

For risky commands, avoid production defaults.

## Document output channels

Include this policy in general docs:

```text
When `--output json` is used, standard output contains only the JSON result.
Logs and diagnostics are written to standard error. Warnings that affect agent
decisions are also included in the JSON `warnings` array.
```

## Documentation checklist

A command is documented for agents when docs include:

- Usage.
- Description.
- Required options.
- Optional options.
- Global options.
- Defaults.
- Output formats.
- Success JSON example.
- Error JSON example.
- Exit codes.
- Error codes.
- Mutation/safety behavior.
- Pagination behavior, if applicable.
- Long-running job behavior, if applicable.
- Examples with `--output json`.
- Version/deprecation notes, if applicable.
