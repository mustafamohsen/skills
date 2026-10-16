# GitHub Automation

## Purpose

Own repository-hosted continuous integration workflows.

## Ownership

- `workflows/agent-first-cli.yml` verifies the public CLI scripts across Windows, macOS, and Linux with Python 3.10 and 3.14.
- Package tests and fixtures remain owned by `skills/agent-first-cli/tests/`.

## Local Contracts

- Use read-only repository permissions and bounded job runtimes.
- Run only synthetic local fixtures; CI must not require production credentials or external services.

## Work Guidance

- Preserve cross-platform process-lifetime coverage when changing runner platforms or Python versions.

## Verification

- Inspect all matrix jobs on the pull request; local macOS success does not establish Windows or Linux correctness.

## Child DOX Index
