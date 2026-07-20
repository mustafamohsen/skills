# Idiomatic Python

Use this reference for Python source, tests, package metadata, and public Python APIs. Idiomatic Python makes data, protocols, ownership, failure, and side effects easy to follow. Formatter, linter, and type-checker success is evidence, not the design goal.

## Establish the Python contract

Before editing, inspect:

- Supported Python versions and interpreters, including `Requires-Python`, environment markers, CI matrices, containers, and runtime pins.
- `pyproject.toml` and other build, package, runtime, and dependency metadata; installed framework and library versions; application entry points and deployment model.
- Formatter, linter, type-checker, test, coverage, and documentation configuration. Do not assume annotations are checked or tests use one particular framework.
- Public import paths, re-exports, `__all__`, call signatures, subclassing hooks, documented exceptions, and downstream consumers.
- Framework conventions for models, dependency injection, request/task lifecycle, transactions, settings, migrations, and generated files.
- Persistence, serialization, process, thread, async, filesystem, network, and foreign-function boundaries.

Use documentation matching the supported version. Syntax and APIs such as positional-only parameters (3.8+), `zip(strict=True)` (3.10+), and `asyncio.TaskGroup`, `ExceptionGroup`, and `except*` (3.11+) are version-gated. Verify alternate-interpreter and library support too. Do not raise the version floor as incidental cleanup.

## Preserve observable Python semantics

A refactor can keep returned values while breaking callers. Add applicable items to the preservation ledger:

- Positional-only, positional-or-keyword, keyword-only, and variadic calling; accepted keyword names; defaults and their evaluation time.
- Mutation, aliasing, copying, object identity, equality, ordering, and hashability.
- Concrete return shape where callers depend on list/tuple/mapping behavior, replay, indexing, or serialization.
- Iteration order, laziness, single-pass consumption, short-circuiting, duplicate evaluation, and when side effects or exceptions occur.
- Exception class, arguments/message where contractual, traceback and explicit/implicit chaining, warnings, logging, and fallback behavior.
- Resource acquisition/release timing, exception suppression, transactions, locks, and partial-failure cleanup.
- Imports, exports, initialization order, circular imports, module caching, registration, and other import-time effects.
- Wire/storage schema, pickle qualified identity/state, backward reads, and custom serialization hooks.
- Coroutine versus ordinary-call behavior, scheduling and completion order, task ownership, context propagation, cancellation, timeouts, and grouped failures.

Do not preserve a security defect merely because it is existing behavior. Keep any approved correction explicit and preserve everything outside that delta.

## Prefer the smallest useful design

### Functions, classes, and modules

Prefer a function when an operation has no durable state, lifecycle, substitutability, or invariant-owning identity. Use a class when construction establishes invariants, instances own resources or evolving state, methods form a cohesive protocol, or a framework expects one. Remove `Manager`, `Service`, `Factory`, and `Helper` layers that only forward calls, but only after checking authorization, transaction, caching, injection, plugin, and compatibility responsibilities.

Organize modules around cohesive domain capabilities, not one class per file. Avoid catch-all `utils.py`, deep facade/re-export graphs, speculative base classes, and configuration-driven indirection that hides ordinary control flow. Keep imports cheap and deterministic; put executable behavior behind a console entry point or `if __name__ == "__main__":`.

```python
# Before
class PriceFormatter:
    def format(self, cents: int) -> str:
        return f"${cents / 100:.2f}"

# After, if the class has no identity, injected policy, subclass contract, or framework role
def format_price(cents: int) -> str:
    return f"${cents / 100:.2f}"
```

Preserve a public class or provide an approved migration when callers construct, patch, subclass, import, or serialize it.

### Duck typing, protocols, and ABCs

Depend on the smallest capability consumed: iteration, mapping access, callability, a standard `collections.abc` interface, or a narrow project contract.

- Use ordinary duck typing when runtime behavior is enough.
- Use `typing.Protocol` to document a static structural boundary without forcing inheritance. Do not add `@runtime_checkable` unless presence-only runtime checks are truly required.
- Use an ABC when shared runtime identity, registration, mixin behavior, or enforced abstract methods are part of the design.
- Use a concrete type when representation or exact behavior matters.

Do not mechanically replace concrete types with protocols. A one-implementation protocol can be justified at an external side-effect boundary, but protocols around every collaborator create coupling and ceremony. An annotation is not runtime validation.

Prefer composition for independently varying transports, storage, clocks, and policies. Use inheritance where framework integration or genuine substitutability is established; avoid deep hierarchies and fragile cooperative `super()` chains.

## Choose data representations deliberately

- A dataclass suits record-like values only when generated initialization, representation, equality, ordering, matching, and hashing match the contract.
- A `NamedTuple` suits small immutable, tuple-compatible records only when indexing, unpacking, and positional compatibility are intentional.
- An ordinary class suits identity-bearing entities, hidden representation, validated construction, computed/lazy attributes, and behavior-heavy objects.
- A dictionary or `TypedDict` suits dictionary-shaped boundaries; `TypedDict` adds static documentation, not runtime validation.

Never mechanically convert a class to `@dataclass`, or add `slots=True` or `frozen=True`. Check inheritance, weak references, dynamic attributes, equality/hash semantics, pickle, framework instrumentation, and supported versions. `frozen=True` is not deep immutability. Do not change a public tuple into a dataclass without checking tuple behavior.

Keep dunder protocols coherent:

- Equality and hashing must agree; adding `__eq__` can make instances unhashable.
- Ordering should represent a real total/partial ordering rather than field accident.
- Return `NotImplemented` for an unsupported peer operand so reflected operations can run.
- Keep `__iter__`, `__len__`, containment, context-manager, and representation behavior mutually sensible.
- Invoke operators and built-ins rather than calling another object's special method directly.

## Defaults, sentinels, mutation, and copies

Default expressions are evaluated once when the function is defined. Use a factory inside the call for per-call mutable state. `None` is an adequate sentinel only when it is not valid input; otherwise use a private identity sentinel.

```python
# Before: values are shared across calls.
def collect(value, values=[]):
    values.append(value)
    return values

# After, if omitted means a fresh list and explicit None is meaningful
_MISSING = object()

def collect(value, values=_MISSING):
    if values is _MISSING:
        values = []
    values.append(value)
    return values
```

This intentionally changes the accidental shared-default behavior; use it only for an approved defect fix or when characterization proves sharing was not contractual. Preserve whether the function mutates and returns the caller's supplied list.

Do not replace `if value is None` with `value or default` unless every falsy value means missing. Treat shallow copy, deep copy, reconstruction, and alias retention as different behaviors: copying can invoke user hooks, break identity sharing, or duplicate more than intended.

## Use clear iteration and control flow

Comprehensions are good for a short, pure mapping/filter with one obvious result. Generators are good for streaming or potentially large inputs when one-shot consumption and delayed work are part of the API. Loops are often clearer for branching, multiple accumulators, mutation, side effects, early exits, or rich error context.

Use built-ins such as `enumerate`, `zip`, `any`, `all`, `min`, `max`, `sum`, and mapping/set operations when they state the operation plainly. Check that:

- Short-circuiting and evaluation order remain the same.
- Input iterators are not consumed twice or materialized unexpectedly.
- Result order and duplicate handling remain contractual.
- Loop `else` behavior is preserved.
- `zip` truncation is intentional; adding `strict=True` changes failure behavior and needs Python 3.10+.

Do not mechanically turn a loop into a comprehension or a list into a generator. Eager results validate and fail earlier, support replay/indexing, and can safely outlive an open resource; lazy results change all of those properties.

## Apply EAFP and LBYL with judgment

Prefer EAFP when the attempted operation is authoritative and a pre-check would duplicate work or introduce a race. Catch only the expected alternative around the smallest expression. Prefer LBYL for cheap stable domain predicates, clearer diagnostics, or operations whose failed attempt is expensive or destructive. Do not apply EAFP everywhere.

```python
# Broad try blocks can hide defects in transform().
try:
    return transform(records[key])
except KeyError:
    return default

# Narrow EAFP, safe only if a missing key is the established fallback.
try:
    record = records[key]
except KeyError:
    return default
else:
    return transform(record)
```

Never use `except Exception: pass` as cleanup. Do not catch `BaseException` for ordinary failures. A pre-check remains appropriate for validation of untrusted data, but should not be presented as protection from a filesystem or concurrency race.

## Preserve exception meaning

Let errors propagate inside a layer unless it can recover or add durable meaning. Translate volatile adapter failures at a meaningful boundary and keep the cause:

```python
try:
    return client.fetch_order(order_id)
except ClientNotFoundError as exc:
    raise OrderNotFound(order_id) from exc
```

This is safe only when `OrderNotFound` is the boundary's promised failure and callers do not rely on the vendor exception. Use bare `raise` to re-raise. Keep the protected block narrow, log once where ownership ends, and preserve exception group structure in concurrent code when relevant. Avoid `return` in `finally`, which can suppress a pending return or exception.

## Make resource ownership lexical

Use context managers to pair acquisition and cleanup when their entry/exit timing and suppression semantics match the contract:

```python
# Before
handle = open(path, encoding="utf-8")
try:
    return handle.read()
finally:
    handle.close()

# After: same acquisition, read, and cleanup scope
with open(path, encoding="utf-8") as handle:
    return handle.read()
```

Use `contextlib.contextmanager` for a simple acquire/yield/release operation and a class for richer state transitions. Use `ExitStack`/`AsyncExitStack` for a dynamic resource set. Ensure cleanup lives in `finally`, and remember a truthy `__exit__` suppresses exceptions. Never return a lazy iterator over a file, cursor, response, or transaction that has already closed; keep the resource open for consumption or transfer ownership explicitly.

## Use typing as static documentation

Type public boundaries, shared data structures, callbacks, and ambiguous returns first; let obvious locals infer. Accept the broadest capability actually supported (`Iterable`, `Sequence`, `Mapping`, callable, or protocol) and return the concrete behavior promised. `Iterable` is wrong if implementation or callers need multiple passes.

- Prefer precise unions and narrowing over spreading `Any`.
- Use aliases for repeated meaningful shapes, not every nested type.
- Keep casts and ignores localized and justified at interoperability seams.
- Do not change runtime acceptance merely to satisfy a checker.
- Validate untrusted CLI, config, JSON, database, and network values at runtime using the project's existing boundary approach.

Annotations are normally not enforced. Runtime annotation introspection, including `typing.get_type_hints()`, may evaluate names and has version-specific behavior; do not reorganize annotations/imports without checking frameworks that inspect them.

## Put dependency seams at side-effect boundaries

Isolate clocks, randomness, environment, filesystem, network, database, subprocess, and broker boundaries when tests or architecture need control. Inject the smallest useful dependency—often a callable, concrete client, or narrow protocol—at the composition root. Keep domain computation pure where practical.

Do not add a dependency-injection framework or wrapper around every standard-library call. Patch where a name is looked up when using mocks, and prefer behavior/contract tests over private call choreography. Import-time I/O and mutable global singletons make seams and process behavior harder to reason about.

## Own async work and cancellation

Calling an async function creates a coroutine object; it does not run until awaited or scheduled. Preserve whether work is sequential, concurrent, bounded, or detached.

- Give every created task an owner, retained reference, exception-observation path, and shutdown policy.
- Use structured concurrency only when child tasks belong to the operation and sibling-cancellation/grouped-failure semantics are correct.
- Do not mechanically convert sync to async, sequential work to concurrent work, or `gather` to `TaskGroup`; each changes call shape, start/order, partial results, cancellation, and exceptions.
- Normally clean up on cancellation and re-raise `asyncio.CancelledError`; do not swallow cancellation in a broad handler. On Python 3.8+, it subclasses `BaseException`; on 3.7, `except Exception` can catch it, so audit older supported runtimes explicitly.
- Bound concurrency and queues; avoid blocking I/O or CPU work on the event loop.
- Keep clients, sessions, streams, locks, subprocesses, and executors alive until all owned work finishes.
- Preserve context variables, timeout scope, lock ordering, and transaction/resource lifetime across awaits.

`TaskGroup` is Python 3.11+ and differs from `gather`: a child failure cancels siblings and failures may emerge as an exception group. Version-check structured-concurrency APIs and use the project's established runtime.

## Preserve imports, serialization, and packaging

Imports execute module code on first load and cache modules in `sys.modules`. Moving or re-exporting names can change initialization order, cycles, registrations, exceptions, startup cost, and public import paths. Keep public facades deliberate and use deprecation/migration when moving stable names.

For JSON and other wire/storage formats, preserve keys, omission versus null, number/string handling, ordering where contractual, encoding, dates, custom hooks, and backward reads. `pickle` can execute arbitrary code and must not accept untrusted data; it also depends on importable qualified names and object state. Renaming/moving classes or changing slots/state can break old payloads. Do not treat pickle and JSON as interchangeable.

Use the repository's established packaging layout. `pyproject.toml` is the standard project metadata location, but migrating legacy metadata or flat layout to `src/` changes builds, editable installs, imports, tooling, and shipped artifacts. Do not perform package-layout migrations mechanically. Build wheel and source distribution and test a clean install when packaging changes are approved.

## Optimize from evidence

Measure realistic workloads with project telemetry, `timeit`, or a profiler before adding caching, concurrency, `slots`, generators, multiprocessing, or specialized collections. Improve algorithms, query/I/O count, batching, and allocation volume before micro-syntax. A list may beat a generator for small or replayed data; a set requires hashability and more memory; process work has startup and serialization cost. Preserve determinism, cache identity/privacy, lifetime, and backpressure.

## Mechanical transformations to reject

Do not apply any of these without explicit semantic and version checks:

- Ordinary class to dataclass, or adding `slots=True`/`frozen=True`.
- List to generator, loop to comprehension, or eager validation to lazy validation.
- Sync to async, sequential to concurrent, or `gather` to `TaskGroup`.
- Concrete dependency to `Protocol` or inheritance to composition solely by style rule.
- LBYL to EAFP everywhere, especially with broad `try` blocks.
- Package metadata or flat/src-layout migration during unrelated refactoring.

## Verification

Use project-local commands and the complete supported interpreter matrix. A proportionate sequence is:

1. Run formatter check/scoped formatting and configured lint rules.
2. Run the configured type checker(s) without broadening suppressions.
3. Run targeted tests, then broader tests for public/shared boundaries.
4. Exercise success, expected failure, empty/falsy values, aliasing/mutation, equality/hashability, order, repeated and partial iteration, and cleanup.
5. Test exception class/chaining and warning/log behavior where contractual.
6. Test cancellation, timeout, partial task failure, shutdown, and resource closure for changed async code.
7. Import affected modules in a fresh process; check public imports, `python -m`/entry points, and import-time output/effects.
8. Read old serialization fixtures and compare new output when persistence changed.
9. Build and inspect wheel/sdist and install them cleanly when package contents or metadata changed.
10. Measure representative workloads when claiming a performance improvement.

Do not invent a toolchain. If a supported interpreter or service is unavailable, run the strongest local subset and name the unverified path.

## Python completion checklist

- Supported Python/interpreter, framework, dependency, and packaging constraints remain satisfied.
- Public imports and signatures preserve calling conventions, defaults, annotations, and promised concrete results.
- Mutation, aliasing, identity, equality, hashing, ordering, laziness, consumption, and exception timing remain deliberate.
- Data representation matches identity, invariants, generated-method behavior, and serialization needs.
- Functions, classes, modules, protocols, ABCs, and dependency seams each earn their abstraction cost.
- Exceptions remain narrow, meaningful, chained where translated, and logged by one owner.
- Resources, transactions, tasks, and cancellation have explicit ownership and cleanup.
- Imports remain deterministic and public names, import-time effects, and old serialized data stay compatible.
- Typing documents static contracts without pretending to validate runtime inputs.
- Performance and concurrency changes are justified by behavior or measurements.
- Project-local checks pass across the relevant supported matrix.

## Primary guidance

Use the documentation for the project's supported version:

- [Python language reference](https://docs.python.org/3/reference/)
- [Python data model](https://docs.python.org/3/reference/datamodel.html)
- [Python tutorial: functions](https://docs.python.org/3/tutorial/controlflow.html#defining-functions)
- [Python tutorial: errors and exceptions](https://docs.python.org/3/tutorial/errors.html)
- [Python glossary: EAFP and LBYL](https://docs.python.org/3/glossary.html)
- [Iterator types](https://docs.python.org/3/library/stdtypes.html#iterator-types)
- [`dataclasses`](https://docs.python.org/3/library/dataclasses.html), [`typing`](https://docs.python.org/3/library/typing.html), [`contextlib`](https://docs.python.org/3/library/contextlib.html), and [`copy`](https://docs.python.org/3/library/copy.html)
- [`asyncio` coroutines and tasks](https://docs.python.org/3/library/asyncio-task.html)
- [Import system](https://docs.python.org/3/reference/import.html)
- [`pickle`](https://docs.python.org/3/library/pickle.html) and [`json`](https://docs.python.org/3/library/json.html)
- [PEP 8](https://peps.python.org/pep-0008/), [PEP 387](https://peps.python.org/pep-0387/), [PEP 484](https://peps.python.org/pep-0484/), and [PEP 544](https://peps.python.org/pep-0544/)
- [PyPA `pyproject.toml` guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/), [layout discussion](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/), and [`Requires-Python` metadata](https://packaging.python.org/en/latest/specifications/core-metadata/#requires-python)
