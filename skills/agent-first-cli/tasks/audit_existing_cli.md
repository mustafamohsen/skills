# Task: Audit an Existing CLI

Use this playbook to evaluate whether an existing CLI is ready for AI-agent consumption.

## Deliverables

Produce:

1. Agent-readiness scorecard.
2. Critical gaps.
3. Recommended fixes by priority.
4. Optional command catalog draft.
5. Optional probe report.

## Step 1: Inspect the public surface

Run or inspect:

```bash
tool --help
tool version --help
tool <resource> --help
tool <resource> <action> --help
```

Capture:

- Command hierarchy.
- Global options.
- Output formats.
- Non-interactive flags.
- Mutating commands.
- Documented exit codes.
- Documented error codes.
- Examples.

## Step 2: Classify commands

For each command, mark:

```text
Command:
Reads state: yes/no
Mutates state: yes/no
Destructive: yes/no
Long-running: yes/no
Needs authentication: yes/no
Can produce large output: yes/no
Supports --output json: yes/no
Supports --no-input or equivalent: yes/no
```

## Step 3: Check baseline criteria

Critical criteria:

- Commands can run without prompts.
- JSON output exists for success and error cases.
- Standard output is clean in JSON mode.
- Errors have stable codes.
- Mutations have preview/safety flow.
- Destructive operations require explicit confirmation.
- Large outputs are paginated or streamable.
- Long operations return operation/job IDs.
- Schemas/capabilities are discoverable.

## Step 4: Probe the live CLI

Create a probe matrix. Start from `examples/probe_matrix.example.json`, then adapt commands.

Run:

```bash
python scripts/afcli_probe.py --cmd "tool" --matrix path/to/probe_matrix.json --out probe-report.json
```

Probe at least:

- `version --output json`
- `capabilities --output json`
- a successful read command
- a missing-required-argument case
- an invalid enum case
- a not-found case
- a mutating command in plan/dry-run mode
- a mutating apply command without confirmation
- a bad flag case

## Step 5: Review JSON quality

For every JSON result, check:

- Top-level `status` exists.
- `status` is `success`, `partial`, or `error`.
- `command` is stable.
- `error.code` exists on errors.
- `warnings` are structured.
- `metadata.schema_version` exists.
- No secret values appear.
- No color codes or progress bars appear in standard output.

## Step 6: Review safety

For each mutating command:

- Is preview available?
- Is preview the default for high-risk commands?
- Is confirmation required for destructive apply?
- Is the confirmation specific to the resource or operation?
- Is an operation ID returned?
- Is rollback support reported?
- Is idempotency supported or intentionally unnecessary?

Open `docs/safety_and_mutation.md` if the CLI has production, billing, identity, data deletion, messaging, or deployment commands.

## Step 7: Produce severity-ranked findings

Use this severity scale:

| Severity | Meaning |
|---|---|
| Critical | Can cause unsafe action, unparseable automation, or unrecoverable agent failure |
| High | Blocks reliable agent use in common workflows |
| Medium | Causes brittleness, ambiguity, or unnecessary retries |
| Low | Documentation or polish issue |

Example finding:

```text
Severity: Critical
Area: Mutation safety
Command: project delete
Finding: The command deletes immediately and only supports `--yes`; no plan/dry-run mode or resource-specific confirmation exists.
Recommendation: Add `--mode plan|apply`; require `--confirm <project-id>` for apply.
```

## Step 8: Recommend a remediation roadmap

Order fixes as:

1. Prevent unsafe mutations.
2. Make errors parseable.
3. Make success output parseable.
4. Add non-interactive operation.
5. Add discovery/schema commands.
6. Add pagination and long-job handling.
7. Improve help and examples.
8. Add compatibility tests.

## Final audit format

Use this structure:

```text
Overall assessment:
Readiness level: not ready / partially ready / mostly ready / agent-first
Top critical gaps:
Scorecard:
Command-specific findings:
Probe results summary:
Recommended roadmap:
Suggested acceptance tests:
```
