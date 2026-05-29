# Safety and Mutation Rules

This document defines safety expectations for state-changing commands in an agent-first CLI.

## Commands that count as mutating

Treat a command as mutating if it can create, update, delete, deploy, migrate, publish, send, charge, transfer, grant, revoke, rotate credentials, alter permissions, or otherwise change external state.

Examples:

```bash
tool project create
tool project update
tool project delete
tool deploy apply
tool email send
tool permission grant
tool database migrate
tool secret rotate
```

## Default rule

A mutating command should either:

1. Run in preview mode by default, or
2. Require an explicit mode such as `--mode plan|apply`.

Recommended:

```bash
tool project delete --id prj_123 --mode plan --output json
tool project delete --id prj_123 --mode apply --confirm prj_123 --output json
```

Avoid making `apply` the silent default for destructive operations.

## Plan/apply protocol

A plan response should include:

```json
{
  "status": "success",
  "command": "project.delete",
  "data": {
    "mode": "plan",
    "operation_class": "destructive",
    "requires_confirmation": true,
    "confirmation_token": "delete:project:prj_123",
    "changes": [
      {
        "action": "delete",
        "resource_type": "project",
        "resource_id": "prj_123",
        "resource_name": "booksqa"
      }
    ],
    "blast_radius": {
      "resources_affected": 12,
      "irreversible": true
    }
  }
}
```

The apply command should include the confirmation token or exact resource ID:

```bash
tool project delete \
  --id prj_123 \
  --mode apply \
  --confirm delete:project:prj_123 \
  --output json
```

## Confirmation standards

Weak confirmation:

```bash
--yes
```

Better confirmation:

```bash
--confirm prj_123
```

Best confirmation for high-risk operations:

```bash
--confirm delete:project:prj_123
```

A confirmation token should be specific enough that an accidental reuse is unlikely.

## Force flags

`--force` should not bypass all safety checks. It should bypass only documented soft checks.

Good uses of `--force`:

- Continue despite non-critical warnings.
- Overwrite a generated file.
- Ignore a stale local cache.

Bad uses of `--force`:

- Delete production resources without confirmation.
- Grant privileges without preview.
- Hide permission or validation errors.

When `--force` is used, the output should state what was bypassed.

## Idempotency

Mutating commands that contact external systems should support retries without duplication.

Recommended flag:

```bash
--idempotency-key <key>
```

Create commands should support one of:

```bash
tool user create --email a@example.com --idempotency-key user:a@example.com
tool user upsert --email a@example.com
tool user create --email a@example.com --dedupe-key email
```

The result should report whether the command created a new resource or reused an existing operation/resource.

```json
{
  "status": "success",
  "command": "user.create",
  "data": {
    "id": "usr_123",
    "created": false,
    "idempotency_key": "user:a@example.com",
    "deduped_from_operation_id": "op_456"
  }
}
```

## Permissions and blast radius

High-risk plan output should identify required permissions and affected resources.

```json
{
  "required_permissions": [
    "project.delete",
    "deployment.revoke"
  ],
  "blast_radius": {
    "environment": "production",
    "resources_affected": 12,
    "estimated_downtime_seconds": 30,
    "irreversible": true
  }
}
```

Agents should be able to decide whether to ask for user confirmation before applying.

## Production guardrails

Commands affecting production, billing, identity, security, data deletion, or external communication should require explicit targeting.

Bad:

```bash
tool deploy
```

Good:

```bash
tool deploy --environment production --mode plan --output json
```

The environment should never silently default to production.

## Rollback

Whenever possible, mutating commands should return rollback information.

```json
{
  "status": "success",
  "command": "migration.apply",
  "data": {
    "operation_id": "op_123",
    "rollback_supported": true,
    "rollback_command": "tool migration rollback --operation-id op_123 --output json"
  }
}
```

If rollback is not supported, say so explicitly:

```json
{
  "rollback_supported": false,
  "rollback_reason": "The command permanently deletes encrypted backups."
}
```

## External communication

Commands that send email, messages, posts, webhooks, or notifications should support preview.

Plan output should include recipients, subject/title, body preview, attachments, and delivery channel.

```json
{
  "mode": "plan",
  "delivery": {
    "channel": "email",
    "recipients": ["redacted:user@example.com"],
    "subject": "Deployment complete",
    "body_preview": "Deployment booksqa-production completed..."
  },
  "requires_confirmation": true
}
```

Do not send external communications from an agent-triggered command unless the agent supplied explicit apply mode and confirmation.

## Safety acceptance checklist

A mutating command passes safety review when:

- It documents whether it mutates state.
- It has a preview path.
- It blocks destructive execution without confirmation.
- It reports blast radius where relevant.
- It returns operation IDs.
- It supports idempotency or documents why not.
- It reports rollback support.
- It fails closed when input is ambiguous.
- It never defaults to production for risky operations.
