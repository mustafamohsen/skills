# Task: Implement or Review One Command

Use this playbook when adding, reviewing, or refactoring a single CLI command.

## Deliverables

For the command under review, produce:

1. Command specification.
2. Input validation rules.
3. Success output shape.
4. Error output shape.
5. Exit-code mapping.
6. Safety behavior, if mutating.
7. Tests.
8. Help examples.

## Step 1: Define the command contract

Record:

```text
Command name:
Stable machine name:
Purpose:
Reads state:
Mutates state:
Destructive:
Long-running:
Can produce large output:
Requires authentication:
Required options:
Optional options:
Default values:
Output formats:
Possible statuses:
Possible error codes:
```

Recommended shell shape:

```bash
tool <resource> <action> [options]
```

Recommended machine name:

```text
resource.action
```

## Step 2: Define inputs precisely

Each option should have:

```text
Name:
Type:
Required:
Default:
Allowed values:
Validation rule:
Example:
Secret/sensitive: yes/no
```

Prefer enums over free-form strings when the domain is bounded.

Good:

```bash
--environment <dev|staging|production>
```

Avoid:

```bash
--environment <string>
```

## Step 3: Define output before coding

Success output should use the standard envelope.

```json
{
  "status": "success",
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

If the command returns a resource, include stable IDs, not only display names.

Bad:

```json
{"name": "Books QA"}
```

Good:

```json
{"id": "prj_123", "name": "Books QA"}
```

## Step 4: Define errors before coding

For every expected failure, define:

```text
Condition:
Exit code:
Error code:
Human message:
Structured details:
Recoverable:
Suggested action:
```

Example:

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
      "Run `tool project list --output json` to inspect available projects."
    ]
  }
}
```

## Step 5: Implement channel discipline

In JSON mode:

- Standard output: one JSON object only.
- Standard error: logs/progress/diagnostics only.
- No spinners, colors, tables, or decorative banners in standard output.
- No prompts when `--no-input` or `--agent` is active.

## Step 6: Add safety if mutating

For mutating commands, support:

```bash
--mode <plan|apply>
```

or:

```bash
--dry-run
```

For destructive commands, require:

```bash
--confirm <token-or-resource-id>
```

For retryable external mutations, support:

```bash
--idempotency-key <key>
```

Plan output should show exact changes and confirmation requirements. Apply output should include an operation ID if useful.

## Step 7: Add pagination or streaming if needed

List commands should support:

```bash
--limit <number>
--cursor <token>
--filter <expression>
--sort <field>
--fields <field1,field2>
```

Streaming commands should support:

```bash
--output jsonl
```

## Step 8: Add tests

Minimum tests for every command:

```text
success_json
missing_required_option_json_error
invalid_value_json_error
bad_flag_json_error
no_color_in_json_stdout
stderr_does_not_break_json
```

For mutating commands:

```text
plan_succeeds_without_mutation
apply_without_confirm_is_blocked
apply_with_confirm_succeeds
idempotency_retry_does_not_duplicate
```

For list commands:

```text
limit_is_respected
cursor_returns_next_page
fields_limits_output_shape
```

## Step 9: Write help examples

Help should include copy-pasteable examples.

Example:

```text
Examples:
  tool project get --id prj_123 --output json
  tool project delete --id prj_123 --mode plan --output json
  tool project delete --id prj_123 --mode apply --confirm prj_123 --output json
```

If a command is dangerous, the help text should say so plainly.

## Step 10: Final command review checklist

The command is ready when:

- Inputs are explicit and validated.
- Success output is stable JSON.
- Errors are stable JSON.
- Exit codes match the taxonomy.
- No interactive prompts appear in agent mode.
- Mutations are safe by default.
- Long operations return IDs.
- Large outputs are bounded.
- Help examples include JSON mode.
- Tests cover success, invalid input, and safety failures.
