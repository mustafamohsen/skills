# Output and Error Design

This document gives the detailed rules for structured output, warnings, partial success, and recoverable errors.

## Output modes

Support at least:

```bash
--output json
--output text
```

Recommended full set:

```bash
--output json
--output jsonl
--output text
--output yaml
```

For agent-first behavior, `json` is the primary contract. Text output can be optimized for humans, but it must not be the only reliable interface.

## Standard output versus standard error

When `--output json` is active:

- Standard output should contain only the JSON result envelope.
- Standard error may contain human-readable logs or diagnostics.
- Warnings that matter to an agent must also appear in the JSON envelope.
- Progress bars, spinners, terminal color codes, and decoration must not appear in standard output.

## Result envelope

Use a stable top-level object:

```json
{
  "status": "success | partial | error",
  "command": "resource.action",
  "data": {},
  "warnings": [],
  "error": null,
  "metadata": {}
}
```

Recommended metadata fields:

```json
{
  "tool_version": "1.4.2",
  "schema_version": "1.0",
  "api_version": "2026-05-01",
  "duration_ms": 431,
  "trace_id": "trace_123"
}
```

Metadata should help an agent decide whether output is compatible, traceable, and recent enough.

## Warning objects

Warnings should be structured, not only free text.

```json
{
  "code": "CACHE_UNAVAILABLE",
  "message": "Cache was unavailable; continuing without cache.",
  "details": {
    "cache_backend": "redis"
  },
  "impact": "Command may be slower than usual."
}
```

Warnings should not change the meaning of `status: success` unless the command produced incomplete or unreliable results. Use `status: partial` for incomplete outcomes.

## Error objects

Use this shape:

```json
{
  "code": "VALIDATION_FAILED",
  "message": "Invalid command input.",
  "details": {
    "fields": [
      {
        "field": "environment",
        "issue": "Expected one of: dev, staging, production.",
        "received": "prodution"
      }
    ]
  },
  "recoverable": true,
  "suggested_actions": [
    "Use `--environment production` or another allowed value."
  ]
}
```

Rules:

1. `code` is stable and machine-readable.
2. `message` is human-readable.
3. `details` contains structured repair information.
4. `recoverable` tells the agent whether retry or correction is plausible.
5. `suggested_actions` should be safe and specific.

Do not include secrets in `details`, `message`, or `suggested_actions`.

## Error code taxonomy

Recommended core codes:

| Code | Use when |
|---|---|
| `INVALID_USAGE` | The command shape or flag usage is wrong |
| `VALIDATION_FAILED` | Input values are syntactically valid but semantically invalid |
| `CONFIGURATION_ERROR` | Config is missing, malformed, or conflicting |
| `AUTHENTICATION_REQUIRED` | No valid identity or credential is available |
| `PERMISSION_DENIED` | Identity exists but lacks permission |
| `RESOURCE_NOT_FOUND` | Referenced resource does not exist |
| `AMBIGUOUS_RESOURCE` | Name or selector matched multiple resources |
| `CONFLICT` | Existing state prevents the operation |
| `UNSAFE_OPERATION` | Operation needs preview, confirmation, or safer flags |
| `NETWORK_ERROR` | Network layer failed |
| `TIMEOUT` | Operation exceeded a timeout |
| `RATE_LIMITED` | External or internal rate limit was reached |
| `PARTIAL_FAILURE` | Some items failed in a batch |
| `UNSUPPORTED_OPERATION` | Operation is not supported in this environment/version |
| `INTERNAL_ERROR` | Unexpected implementation fault |

Project-specific codes may extend this set, but do not rename the core concepts unnecessarily.

## Field-level validation

For bad inputs, include field-level errors.

```json
{
  "status": "error",
  "command": "project.create",
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Invalid project configuration.",
    "details": {
      "fields": [
        {
          "field": "name",
          "issue": "Must match ^[a-z][a-z0-9-]{2,31}$.",
          "received": "My Project"
        },
        {
          "field": "region",
          "issue": "Expected one of: eu, us, apac.",
          "received": "europe"
        }
      ]
    },
    "recoverable": true,
    "suggested_actions": [
      "Use a lowercase dash-separated project name.",
      "Use `--region eu`, `--region us`, or `--region apac`."
    ]
  }
}
```

## Ambiguity handling

Do not prompt the agent to choose from a list interactively.

Bad:

```text
Which project do you mean?
1. booksqa
2. booksqa-old
```

Good:

```json
{
  "status": "error",
  "command": "project.get",
  "error": {
    "code": "AMBIGUOUS_RESOURCE",
    "message": "Multiple projects matched selector `booksqa`.",
    "details": {
      "matches": [
        {"id": "prj_1", "name": "booksqa"},
        {"id": "prj_2", "name": "booksqa-old"}
      ]
    },
    "recoverable": true,
    "suggested_actions": [
      "Repeat the command with `--id prj_1` or `--id prj_2`."
    ]
  }
}
```

## Partial success

Batch operations should never report `success` when some items failed.

```json
{
  "status": "partial",
  "command": "file.upload_batch",
  "data": {
    "succeeded": 97,
    "failed": 3,
    "failed_items": [
      {
        "path": "a.mov",
        "error_code": "FILE_TOO_LARGE",
        "recoverable": false
      },
      {
        "path": "b.txt",
        "error_code": "NETWORK_ERROR",
        "recoverable": true
      }
    ],
    "retry_command": "tool file upload-batch --retry-from op_123 --output json"
  },
  "warnings": [],
  "error": null
}
```

Use exit code `9` for partial failure if the calling environment distinguishes it.

## JSON Lines for streams

Use `jsonl` for long-running streams or event feeds.

Each line should be independently parseable:

```jsonl
{"type":"start","operation_id":"op_123"}
{"type":"progress","current":10,"total":100}
{"type":"item","id":"item_9","status":"processed"}
{"type":"warning","code":"SLOW_DEPENDENCY","message":"Dependency latency is high."}
{"type":"summary","status":"success","processed":100,"failed":0}
```

Avoid printing a mixture of JSON Lines and human logs to standard output.

## Redaction

Secrets must be redacted by default.

Recommended redaction shape:

```json
{
  "credential_present": true,
  "credential_source": "env:MYTOOL_API_KEY",
  "credential_preview": "redacted:sk_...9f3a"
}
```

Never reveal full tokens, passwords, private keys, session cookies, or OAuth refresh tokens in JSON output, logs, trace files, or suggested actions.

## Compatibility rules

Within a major schema version:

- Adding optional fields is safe.
- Removing fields is breaking.
- Renaming fields is breaking.
- Changing field types is breaking.
- Changing stable error codes is breaking.
- Changing success into partial/error semantics is breaking unless previously documented as possible.

Document deprecations inside `warnings`:

```json
{
  "code": "FIELD_DEPRECATED",
  "message": "`project_name` is deprecated; use `project.id`.",
  "deprecated_since": "1.3.0",
  "removal_version": "2.0.0"
}
```
