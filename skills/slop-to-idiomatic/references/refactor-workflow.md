# Behavior-Preserving Refactor Workflow

Use this reference for every invocation. It governs how to change the code; the language and framework references govern what idiomatic code looks like.

## 1. Establish the contract before editing

Translate the user's scope into a short working contract:

- Target files, subsystem, or diff.
- Requested behavior changes, if any.
- Behaviors that must remain unchanged.
- Permitted API, schema, dependency, or architecture changes.
- Required verification and practical time constraints.

Do not treat “clean up” as permission to change UX, public names, wire formats, error messages, logging, retries, caching, or performance characteristics.

## 2. Read outward from the target

Inspect enough context to understand why the code has its current shape:

1. Repository instructions and current working-tree changes.
2. Build, format, lint, type-check, and test commands.
3. The target implementation and its nearest tests.
4. Direct callers and callees.
5. Public exports, schemas, generated types, and persistence/network boundaries.
6. Framework and dependency versions that constrain valid idioms.
7. Nearby well-maintained code that demonstrates local conventions.

Local consistency usually beats a generic style preference. Do not copy a local pattern when it is clearly a defect the refactor is meant to remove.

## 3. Build a preservation ledger

Write down the observable properties that could be lost in a “harmless” rewrite. Include applicable items:

| Boundary | Preserve or explicitly change |
|---|---|
| API | Export names, parameter and return types, overloads, trait bounds, props, route IDs |
| Data | JSON shape, field omission, nullability, enum tags, search params, DB writes |
| Failure | Error type, status/code/message, panic/throw behavior, fallback and retry policy |
| Effects | I/O, logging, analytics, subscriptions, cleanup, transaction scope |
| Time/order | Evaluation order, event order, concurrency, cancellation, debounce, cache lifetime |
| Identity | Referential equality, React keys, stable IDs, ownership and borrowing expectations |
| Security | Authentication, authorization, validation, secret placement, trust boundaries |
| Runtime | Client/server execution, SSR/hydration, platform assumptions, feature flags |
| Performance | Hot paths, allocation/copy behavior, render frequency, query count, streaming |

Use tests or focused probes to lock down high-risk ledger entries. Snapshot tests are useful only when the snapshot represents a meaningful contract.

## 4. Diagnose beyond lint

Look for generated-code tendencies that syntax tools rarely settle:

- Abstractions with one accidental use, wrapper chains, and layers that only rename operations.
- Repeated near-identical code that should share a domain operation—or forced deduplication that hides meaningful differences.
- Primitive obsession, boolean clusters, sentinel values, stringly typed states, and impossible state combinations.
- Types that describe implementation mechanics instead of domain guarantees.
- Broad catches, swallowed context, invented defaults, and failures converted into ambiguous success values.
- Work performed in the wrong layer: view logic in services, persistence in UI, server secrets in shared modules.
- Mutable or duplicated state that requires synchronization.
- Clever generic helpers that reduce local clarity or weaken inference.
- Comments that narrate syntax, stale scaffolding, placeholder names, and needless “future-proofing.”
- Unnecessary async, allocations, clones, effects, memoization, caches, or serialization hops.
- Inconsistent use of the framework's own routing, data, lifecycle, validation, and error primitives.

Classify each finding as correctness risk, maintenance cost, ecosystem mismatch, or cosmetic issue. Fix in that order.

## 5. Choose the verification loop honestly

### Red → green → refactor

Use when correcting a bug or intentionally changing behavior. First add a focused test that fails for the intended reason. Make the smallest behavior change that passes, then improve the structure while keeping it green.

### Green → refactor → green

Use for a pure refactor with trustworthy coverage. Confirm the relevant tests pass before editing. Make one coherent structural change at a time and rerun the narrowest meaningful checks.

### Characterize → refactor → characterize

Use when current behavior must be preserved but is untested. Add tests that pass against the current implementation and capture externally relevant behavior, including edge cases from the preservation ledger. Avoid freezing private implementation details.

If the code is too entangled to test, first insert the smallest behavior-neutral seam, verify it, then add characterization coverage. Do not create a fake failing test for behavior that already works.

### Tests are inapplicable

Examples include type-only reshaping, comments, generated artifacts that should not be hand-edited, or infrastructure unavailable in the current environment. Use the strongest relevant substitute: compiler/type checker, formatter check, build, contract comparison, static search, or a minimal reproducible probe. State the limitation.

## 6. Refactor in risk-ordered slices

Prefer this sequence when applicable:

1. Lock down behavior and boundaries.
2. Improve names and make control flow explicit.
3. Remove duplication or indirection only after intent is visible.
4. Improve domain types and invalid-state prevention.
5. Move work to the correct architectural/framework boundary.
6. Delete obsolete code and comments.
7. Optimize only when the current design or evidence warrants it.

Keep the code runnable between slices. Avoid mixing formatting churn with semantic edits when it obscures review.

## 7. Apply senior-level judgment

- Prefer obvious code over compressed code.
- Keep abstractions at one level of detail; extract concepts, not line counts.
- Preserve deliberate asymmetry. Similar-looking cases may have different domain rules.
- Make illegal states unrepresentable when the benefit outweighs migration cost.
- Parse and validate at untrusted boundaries; keep the interior strongly typed.
- Make ownership of state, effects, and errors apparent.
- Use ecosystem vocabulary so maintainers can predict where behavior lives.
- Delete code made redundant by the refactor; do not leave compatibility shims without a consumer.
- Do not turn every function into a utility, every value into a class, or every branch into a pattern abstraction.

## 8. Final verification

Run the smallest complete check set supported by the repository:

1. Formatter in check or scoped write mode.
2. Compiler/type checker.
3. Targeted unit/component/integration tests.
4. Broader tests for shared or boundary code.
5. Linter and build when they cover different failure classes.
6. Final diff review against the preservation ledger.

Search for stale symbol names, unused compatibility paths, debug output, broad suppressions, unsafe casts, and accidentally edited generated files.

## Handoff format

Report:

- The structural problems removed and the ecosystem idioms adopted.
- Observable behavior or boundaries deliberately preserved.
- Any intentional behavior change, separately identified.
- Tests/checks run and their result.
- Remaining risks, unverified paths, or follow-up work—without inventing work to sound thorough.
