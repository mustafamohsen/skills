---
name: slop-to-idiomatic
description: Refactors existing AI-generated code into clear, conventional, language- and framework-idiomatic code while preserving its observable behavior and boundaries. User-invoked only; use only when the user explicitly invokes `$slop-to-idiomatic` or `/slop-to-idiomatic`, never automatically.
user-invocable: true
disable-model-invocation: true
argument-hint: "[path, diff, or refactor scope]"
---

# Slop to Idiomatic

Turn working but awkward generated code into code a senior maintainer would expect to inherit. Preserve functionality, contracts, boundaries, purpose, and results unless the user explicitly requests a behavior change.

## Invocation gate

Run this skill only after explicit user invocation. If it was loaded implicitly, do not inspect or modify the target; ask the user to invoke `$slop-to-idiomatic` explicitly.

## Load the minimum context

Always read [`references/refactor-workflow.md`](references/refactor-workflow.md). Then read only the applicable idiom references:

| Code in scope | Read |
|---|---|
| C++ translation units or headers compiled as C++ | [`references/cpp.md`](references/cpp.md) |
| JavaScript (`.js`, `.mjs`, `.cjs`) | [`references/javascript.md`](references/javascript.md) |
| JavaScript JSX | [`references/javascript.md`](references/javascript.md), plus the applicable framework reference |
| Python | [`references/python.md`](references/python.md) |
| Rust | [`references/rust.md`](references/rust.md) |
| TypeScript (`.ts`, `.mts`, `.cts`) | [`references/typescript.md`](references/typescript.md) |
| TypeScript JSX (`.tsx`) | [`references/typescript.md`](references/typescript.md), plus the applicable framework reference |
| React | [`references/react.md`](references/react.md), plus JavaScript or TypeScript as applicable |
| TanStack Start | [`references/tanstack-start.md`](references/tanstack-start.md), React, and TypeScript |

When several apply, reconcile them in this order: repository conventions and supported versions, framework rules, language idioms, then general preferences. Never force a reference pattern that conflicts with the project's established architecture or version.

## Required operating rules

1. Read repository instructions, the scoped code, callers, tests, configuration, and dependency versions before proposing edits.
2. Build a preservation ledger for public APIs, types, errors, side effects, ordering, timing, serialization, persistence, security boundaries, and client/server placement.
3. Separate lint-level cleanup from structural idiom work. Focus on ownership, state, data flow, domain modeling, abstraction level, framework boundaries, and failure semantics.
4. Prefer the smallest coherent refactor. Do not rewrite unrelated code, introduce speculative abstractions, swap libraries, or broaden scope to make the result look cleaner.
5. Choose the testing loop deliberately:
   - Behavior change or bug fix: red → green → refactor.
   - Pure refactor with adequate tests: green → refactor → green.
   - Pure refactor without coverage: add passing characterization tests, then refactor in small green steps.
   - If tests are inapplicable, explain why and use focused static checks plus careful before/after reasoning.
6. Validate after each meaningful slice with the repository's own formatter, type checker/compiler, targeted tests, and lint rules. Run broader tests when risk justifies them.
7. Review the final diff for accidental contract changes and generated-code churn. Report what became idiomatic, what was deliberately preserved, and the exact checks run.

## Definition of done

The result is simpler to read in the host ecosystem, has fewer invalid states and synchronization paths, respects project-local conventions, preserves agreed behavior, and passes proportionate verification. “Different” or “shorter” alone is not an improvement.
