# Agent-First CLI Tests

## Purpose

Own black-box regression tests for the package's public JSON-emitting scripts.

## Ownership

- Tests invoke shipped scripts through their subprocess interfaces.
- Test fixtures and mock CLIs used only by these tests belong in this subtree.

## Local Contracts

- Assert observable JSON output, standard-error behavior, and process exit status rather than helper implementation details.
- Use only the Python standard library so package verification remains zero-install.

## Work Guidance

- Add one behavior-focused regression at a time and keep expected values independent of implementation logic.

## Verification

- Run `python3 -m unittest discover -s skills/agent-first-cli/tests -p 'test_*.py'` from the repository root.

## Child DOX Index
