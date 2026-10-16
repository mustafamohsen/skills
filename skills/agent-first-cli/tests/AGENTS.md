# Agent-First CLI Tests

## Purpose

Own black-box regression tests for the package's public JSON-emitting scripts.

## Ownership

- Tests invoke shipped scripts through their subprocess interfaces.
- Test fixtures and mock CLIs used only by these tests belong in this subtree.
- Mutation-gate tests use disposable local resources and verify that rejection happens before any invocation.

## Local Contracts

- Assert observable JSON output, standard-error behavior, and process exit status rather than helper implementation details.
- Use only the Python standard library so package verification remains zero-install.
- Redaction tests use synthetic secrets only and check both stdout and file reports, including command metadata and failure details.

## Work Guidance

- Add one behavior-focused regression at a time and keep expected values independent of implementation logic.
- Process-lifetime fixtures use bounded workers and temporary resources. Check descendant cleanup after timeout, completion, and interruption on POSIX and Windows; never rely on local macOS results alone.

## Verification

- Run `python3 -m unittest discover -s skills/agent-first-cli/tests -p 'test_*.py'` from the repository root.

## Child DOX Index
