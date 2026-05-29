# Task: Design a New Agent-First CLI

Use this playbook when the CLI is still being designed or when a redesign is possible.

## Deliverables

Produce these artifacts:

1. Command catalog.
2. Global option policy.
3. Output and error contract.
4. Safety model for mutations.
5. Discovery and documentation plan.
6. Test matrix.
7. Compatibility policy.

Use `templates/command_catalog.template.json` as a starting point.

## Step 1: Identify agent jobs

Write down the real jobs an agent will perform.

Good job statements:

- "Create a project after validating configuration."
- "Inspect deployment status and retry failed jobs."
- "Search resources by stable ID or exact name."
- "Preview and apply a database migration."

Avoid designing around vague commands such as "manage things" or "do setup".

For each job, record:

```text
Job:
Primary actor:
Inputs:
Expected output:
Failure modes:
Mutation risk:
Long-running risk:
Pagination/streaming risk:
```

## Step 2: Define resource/action commands

Prefer:

```bash
tool <resource> <action>
```

Examples:

```bash
tool project list
tool project get
tool project create
tool project update
tool project delete
tool deployment plan
tool deployment apply
tool job status
tool job cancel
```

For machine metadata, use dotted command names:

```text
project.list
project.get
project.create
deployment.apply
```

Avoid inconsistent naming:

```bash
tool list-projects
tool project-info
tool make project
tool rm-project
```

## Step 3: Define global flags

Recommended baseline:

```bash
--output <json|jsonl|text|yaml>
--agent
--no-input
--no-color
--quiet
--verbose
--debug
--log-level <error|warn|info|debug|trace>
--config <path>
--profile <name>
--cwd <path>
--timeout <duration>
--trace-id <id>
```

Decide whether `--agent` is supported. If yes, define it as a transparent bundle, for example:

```bash
--output json --no-input --no-color --log-level warn
```

Do not let `--agent` bypass safety confirmation.

## Step 4: Define the output contract

Use the standard envelope unless the project already has a stable alternative.

```json
{
  "status": "success | partial | error",
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

For deeper rules, open `docs/output_and_errors.md`.

## Step 5: Define error taxonomy

Start with the core error codes:

```text
INVALID_USAGE
VALIDATION_FAILED
CONFIGURATION_ERROR
AUTHENTICATION_REQUIRED
PERMISSION_DENIED
RESOURCE_NOT_FOUND
AMBIGUOUS_RESOURCE
CONFLICT
UNSAFE_OPERATION
NETWORK_ERROR
TIMEOUT
RATE_LIMITED
PARTIAL_FAILURE
UNSUPPORTED_OPERATION
INTERNAL_ERROR
```

For each command, list likely error codes and the structured `details` fields the agent can use to recover.

## Step 6: Define mutation safety

For each mutating command, require one of:

```bash
--mode plan|apply
--dry-run
```

For destructive/high-risk commands, also require:

```bash
--confirm <token-or-resource-id>
```

For externally retried operations, add:

```bash
--idempotency-key <key>
```

Use `docs/safety_and_mutation.md` when the command changes production, billing, permissions, data, messages, or deployments.

## Step 7: Define discovery commands

Recommended minimum:

```bash
tool version --output json
tool capabilities --output json
tool commands --output json
tool command-schema <command> --output json
tool config effective --output json
tool doctor --output json
```

Discovery output should let an agent answer:

- What commands exist?
- Which flags are required?
- Which commands mutate state?
- Which output formats are supported?
- Which error codes may occur?
- Which features are experimental or deprecated?

## Step 8: Draft the command catalog

Use `templates/command_catalog.template.json`.

Then lint it:

```bash
python scripts/afcli_schema_lint.py path/to/command_catalog.json
```

Fix critical issues first, then warnings.

## Step 9: Define tests before implementation

For each command, specify tests for:

- Success with `--output json`.
- Missing required input.
- Invalid enum value.
- Missing authentication or configuration, if relevant.
- Ambiguous resource selection.
- Resource not found.
- Timeout behavior, if relevant.
- Plan mode for mutating commands.
- Apply mode blocked without confirmation.
- Apply mode success with confirmation.

Use `tasks/test_cli.md` to create the test matrix.

## Step 10: Produce the design summary

The final design summary should include:

```text
CLI name:
Primary agent jobs:
Command hierarchy:
Global flags:
Output formats:
Standard result envelope:
Error taxonomy:
Mutation safety model:
Discovery commands:
Pagination/streaming model:
Long-running operation model:
Configuration model:
Versioning policy:
Initial test matrix:
Open risks:
```
