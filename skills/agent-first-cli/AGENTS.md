# Agent-First CLI Package

## Purpose

Provide guidance, tasks, schemas, examples, and probes for designing and auditing CLIs consumed primarily by agents.

## Ownership

- `SKILL.md` owns the package workflow and routing.
- `docs/` owns detailed contracts; `tasks/` owns task playbooks; `templates/` and `examples/` own machine-readable artifacts; `scripts/` owns local probes.
- `README.md` and `manifest.txt` own package presentation and shipped-file inventory.

## Local Contracts

- Keep schemas, templates, examples, docs, and probe behavior aligned.
- Preserve machine-readable stdout and safety semantics when changing scripts or contracts.

## Work Guidance

- Prefer targeted changes to the owning artifact and update dependent examples or docs in the same change.

## Verification

- Run the package probe and schema-lint scripts when their covered contracts change.
- Confirm every manifest entry exists and intended package files are listed.

## Child DOX Index
