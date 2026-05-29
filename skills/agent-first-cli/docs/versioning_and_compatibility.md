# Versioning and Compatibility

Agent-first CLIs need stronger compatibility discipline than human-only tools because agents parse outputs, error codes, and command schemas literally.

## Version surfaces

Expose all relevant versions:

```bash
tool version --output json
```

Recommended output:

```json
{
  "status": "success",
  "command": "version",
  "data": {
    "tool_name": "mytool",
    "cli_version": "1.4.2",
    "schema_version": "1.0",
    "api_version": "2026-05-01",
    "build": {
      "commit": "abc1234",
      "date": "2026-05-01"
    }
  },
  "warnings": [],
  "error": null
}
```

## What is a breaking change?

For an agent-first CLI, these are breaking changes:

- Removing a command.
- Renaming a command.
- Removing a flag or option.
- Renaming a flag or option.
- Changing a default in a way that changes behavior.
- Changing a JSON field type.
- Removing a JSON field.
- Renaming a JSON field.
- Changing `status` semantics.
- Changing stable error codes.
- Moving diagnostics from standard error into standard output in JSON mode.
- Adding an interactive prompt to a previously non-interactive command.
- Making a previously safe preview command mutate state.
- Making a command require network/auth/config when it did not before, unless documented.

Adding optional fields is generally safe. Adding new commands is safe. Adding new error codes can be safe if callers are expected to handle unknown codes within a broad exit-code class.

## Deprecation pattern

When deprecating a field, flag, or command, include structured warnings.

```json
{
  "warnings": [
    {
      "code": "FLAG_DEPRECATED",
      "message": "`--project-name` is deprecated; use `--project-id`.",
      "deprecated_since": "1.4.0",
      "removal_version": "2.0.0",
      "replacement": "--project-id"
    }
  ]
}
```

Deprecations should appear in:

- `--help`
- `commands --output json`
- `command-schema <command> --output json`
- Runtime output when the deprecated feature is used
- Release notes

## Schema versioning

Use semantic compatibility, even if the schema version is not exactly semantic versioning.

Recommended:

```text
schema_version: 1.0
```

Rules:

- `1.0` to `1.1`: additive changes only.
- `1.x` to `2.0`: breaking changes allowed with migration notes.
- Pre-1.0 schemas may change, but should be labelled experimental.

## Experimental commands

Experimental commands should be marked clearly in machine-readable discovery output.

```json
{
  "name": "model.tune",
  "status": "experimental",
  "stability": "unstable",
  "breaking_changes_possible": true
}
```

Do not mix experimental fields silently into stable output without marking them.

## Capability negotiation

Agents should be able to discover feature support.

```bash
tool capabilities --output json
```

Example:

```json
{
  "status": "success",
  "command": "capabilities",
  "data": {
    "supports": {
      "json_output": true,
      "jsonl_output": true,
      "non_interactive": true,
      "plan_apply": true,
      "idempotency_keys": true,
      "command_schemas": true,
      "effective_config": true
    },
    "output_formats": ["json", "jsonl", "text"],
    "schema_versions": ["1.0"]
  }
}
```

## Migration notes

For major changes, provide a machine-readable migration summary.

```bash
tool migration-notes --from 1.x --to 2.0 --output json
```

Example:

```json
{
  "status": "success",
  "command": "migration-notes",
  "data": {
    "from": "1.x",
    "to": "2.0",
    "breaking_changes": [
      {
        "type": "field_removed",
        "old": "project_name",
        "new": "project.id",
        "impact": "Update JSON parsers."
      }
    ]
  }
}
```

## Compatibility test matrix

Before release, test:

1. Stable commands still exist.
2. Required flags remain valid.
3. JSON envelopes still parse.
4. Error codes are unchanged unless intentionally deprecated.
5. `--output json` has no decorative standard output.
6. Deprecated items still include replacement guidance.
7. Mutating commands still require preview/confirmation.
8. `version`, `capabilities`, `commands`, and `command-schema` still work.

## Release checklist

For each release:

- Update `tool version --output json`.
- Update schema version only when needed.
- Run dynamic CLI probes.
- Run command catalog linting.
- Generate or update release notes.
- Confirm all new commands have examples.
- Confirm all new error codes are documented.
- Confirm no new interactive prompt appears in agent mode.
