# Skill Packages

## Purpose

Own the reusable, independently installable skill packages published by this repository.

## Ownership

- Each direct child package owns its runtime instructions, supporting references, documentation, metadata, and manifest.
- Root repository discovery and support summaries remain owned by the root `README.md` and `skills.sh.json`.

## Local Contracts

- Every package has `SKILL.md` with valid frontmatter and a `manifest.txt` describing shipped files.
- Keep routing documents concise and use supporting files for progressively disclosed detail.
- Preserve invocation and safety policies when extending an existing package.

## Work Guidance

- Follow established package structure; avoid cross-package dependencies unless they are an explicit repository design.
- Keep package README, router, and manifest descriptions synchronized.

## Verification

- Confirm every manifest entry exists and every intended package artifact is listed.
- Resolve local Markdown links and run package-provided checks or scripts where applicable.

## Child DOX Index

- [`agent-first-cli/AGENTS.md`](agent-first-cli/AGENTS.md) — agent-oriented CLI design and audit package.
- [`slop-to-idiomatic/AGENTS.md`](slop-to-idiomatic/AGENTS.md) — explicit behavior-preserving refactoring package.
