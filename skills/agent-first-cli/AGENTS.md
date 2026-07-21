# Agent-First CLI Package

## Purpose

Provide guidance, tasks, schemas, examples, and probes for designing and auditing CLIs consumed primarily by agents.

## Ownership

- `SKILL.md` owns the package workflow and routing.
- `docs/` owns detailed contracts; `tasks/` owns task playbooks; `templates/` and `examples/` own machine-readable artifacts; `scripts/` owns local probes.
- `tests/` owns black-box regression coverage for the shipped scripts.
- `README.md` and `manifest.txt` own package presentation and shipped-file inventory.

## Local Contracts

- Keep schemas, templates, examples, docs, and probe behavior aligned.
- Preserve machine-readable stdout and safety semantics when changing scripts or contracts.

## Work Guidance

- Prefer targeted changes to the owning artifact and update dependent examples or docs in the same change.

## Verification

- Run `python3 -m unittest discover -s skills/agent-first-cli/tests -p 'test_*.py'` when public script behavior changes.
- Run the package probe and schema-lint scripts when their covered contracts change.
- Confirm every manifest entry exists and intended package files are listed.

## Child DOX Index

- [`tests/AGENTS.md`](tests/AGENTS.md) — black-box public-script regression tests.
