# Idiomatic JavaScript

Use this reference for `.js`, `.mjs`, `.cjs`, and JavaScript JSX. It covers runtime language and module semantics plus design choices that formatters, linters, and optional type tooling cannot settle. Use a separate framework reference for JSX lifecycle and rendering rules.

## Establish the host contract

Before editing, inspect:

- Every execution host and supported version: browsers, Node.js, workers, edge/serverless, embedded runtimes, test runners, and build-time execution.
- ESM versus CommonJS, strict-mode expectations, file extensions, package `type` and `exports`, entry points, conditional exports, and public import paths.
- Bundler, transpiler, JSX transform, polyfills, syntax target, and whether source or emitted output is shipped.
- Framework and JSX runtime, including whether JSX is React, another framework, or a custom transform.
- Public exports, globals, plugin hooks, serialization formats, and the complete test/build matrix.

Use documentation matching those hosts. Do not raise the runtime floor, change module interpretation, or assume a current engine feature is available as incidental cleanup.

## Preserve observable JavaScript semantics

A rewrite that returns the same happy-path value can still break its contract. Add applicable concerns to the preservation ledger:

- Evaluation count and left-to-right order, including computed properties, defaults, getters, coercion hooks, and short-circuiting.
- Coercion and truthiness; distinctions among `null`, `undefined`, absent properties, array holes, empty strings, zero, `false`, and `NaN`.
- `this`, `arguments`, `new` constructibility, `new.target`, function identity/name/length, and callback receiver conventions.
- Closure capture, per-iteration bindings, temporal dead zones, hoisting, and when defaults or class fields run.
- Prototype identity, descriptors, enumerability, symbols, accessors, proxies, and own versus inherited properties.
- Mutation, aliases, shallow/deep copying, referential equality, key order, and collection key equality.
- Iterator laziness, single-pass consumption, early closing, generator cleanup, and exception timing.
- Thrown value/type/message where contractual, stack/cause, `finally`, cleanup, and error masking.
- Promise identity, settlement, microtask timing, start order, concurrency, partial failure, cancellation, and unhandled rejection ownership.
- Module resolution, initialization/evaluation order, cycles, live bindings, export shape, import-time effects, and loader interop.
- Listener identity, registration/removal order, resource lifetime, timers, handles, streams, and abort ownership.
- JSON omission/coercion, custom `toJSON`, storage/wire compatibility, validation, and prototype-pollution boundaries.

Do not preserve an approved security defect. Keep that correction explicit and preserve everything outside it.

## Prefer the smallest useful design

### Functions, objects, classes, and modules

Prefer a function or cohesive module for stateless operations. Use a class when instances own identity, invariants, lifecycle, private state, polymorphism, or a framework contract. Prefer composition for independently varying policies or adapters; retain inheritance when substitutability or framework integration is real.

Remove `Manager`, `Service`, `Helper`, factory, and wrapper layers that only forward calls, but first check authorization, transaction, caching, instrumentation, injection, mocking, subclassing, and public compatibility roles.

```js
// Before
class PriceFormatter {
  format(cents) {
    return `$${(cents / 100).toFixed(2)}`
  }
}

// After, only if construction, identity, injection, and subclassing are irrelevant
function formatPrice(cents) {
  return `$${(cents / 100).toFixed(2)}`
}
```

Organize modules around cohesive capabilities. Avoid catch-all utilities and barrel/facade chains that hide cycles or side effects. Keep import-time work deliberate and deterministic.

### Parameters and runtime state

Use a few obvious positional parameters. Use an options object when arguments are numerous, optional, easy to swap, or meaningfully expected to evolve—not to wrap every single argument.

Represent runtime state so valid variants are explicit. A tag plus variant-specific fields can be clearer than correlated booleans, but JavaScript objects remain mutable and unvalidated unless code enforces the invariant. Do not copy TypeScript discriminated-union advice as though it provides runtime guarantees.

Use plain objects for fixed string-keyed records and interoperability with JSON. Use `Map` when arbitrary key identity, a prototype-free collection API, or insertion order without ordinary objects' integer-index grouping is the actual model. Use `Set` for uniqueness. Check serialization, equality, enumeration, prototype exposure, and existing callers before changing representations.

## Make control flow state intent

Guard clauses are useful when they remove nesting without scattering one invariant. Use the construct that exposes the operation:

- `map` for one output per input, `filter` for selection, and `find`/`some`/`every` for short-circuiting queries.
- A loop for multiple accumulators, branching, side effects, `break`/`continue`, await sequencing, or clearer mutation.
- A generator for intentional lazy, single-pass production with a clear resource lifetime.

Do not compress multi-stage business logic into a dense `reduce` or array-method chain. Preserve holes, callback arguments, receiver, mutation, short-circuiting, and exception timing when changing iteration.

### Missing is not merely falsy

```js
// Before: 0, false, and '' all select the fallback.
const retries = options.retries || 3

// After, only when exactly null or undefined means missing.
const retries = options.retries ?? 3
```

This is not a style substitution. Likewise, optional chaining is appropriate only when absence is an accepted path; it can hide an invariant violation and changes whether later expressions run.

Do not mechanically replace `==` with `===`. Strict equality is normally clearer for new comparisons, but existing abstract equality can intentionally perform coercion (`value == null` is also a concise null-or-undefined check). Characterize accepted inputs before changing it.

## Preserve functions, receivers, and closures

Ordinary and arrow functions are not interchangeable. Arrows capture lexical `this` and `arguments`, cannot be constructors, and have different prototype behavior. Ordinary functions receive a call-site-dependent receiver.

```js
const counter = {
  value: 0,
  increment() {
    this.value += 1
  },
}

// Unsafe: the receiver is lost when the callback is invoked plainly.
queueMicrotask(counter.increment)

// Safe when the callback should target this counter; retain the wrapper identity
// if it must later be removed from a listener registry.
queueMicrotask(() => counter.increment())
```

Before extracting a method, bind or wrap it only if that receiver policy is intended. For event listeners, store the bound/wrapper function so removal uses the same identity. Preserve dynamic receiver APIs that intentionally use `.call`, `.apply`, or framework binding.

Closures capture bindings, not frozen values. Check loop binding kind, later mutation, lifetime, and retained resources before moving functions or replacing a closure with module state. Avoid per-request or per-user mutable module globals.

## Respect objects, prototypes, and copies

Object operations differ:

- Spread and `Object.assign` are shallow, read enumerable own source properties, and may invoke getters; assignment targets can invoke setters while object spread defines data properties on a fresh object.
- `structuredClone` supports a defined set of cloneable values, can reject functions and platform objects, does not preserve every descriptor/prototype contract, and may transfer selected resources.
- A class/prototype instance is not interchangeable with a plain object; methods, private fields, brands, descriptors, and `instanceof` may matter.
- `Object.keys`, `for...in`, `Reflect.ownKeys`, and ownership checks observe different key sets.

Never substitute spread, `Object.assign`, JSON round-tripping, or `structuredClone` merely because each appears to “copy an object.” Decide whether aliases, prototypes, accessors, symbols, descriptors, cycles, and transfer behavior must remain.

At untrusted object-key boundaries, validate keys and prefer null-prototype dictionaries or `Map` where appropriate. Block dangerous paths such as `__proto__`, `constructor`, and `prototype` in recursive assignment/merge code; do not treat a TypeScript type or truthy check as runtime validation.

## Keep iteration and resources deliberate

Iterables are not necessarily arrays. Materializing with spread or `Array.from` changes memory use, failure time, infinity handling, and one-shot consumption. Replacing a loop with an array chain may change sparse-array behavior and eliminate early exit.

Abrupt completion of `for...of` can call an iterator's `return()` for cleanup. If rewriting manual iteration or generators, preserve closing behavior. Do not return a lazy iterable over a stream, cursor, lock, or transaction whose owner has already cleaned it up.

Own timers, subscriptions, streams, file handles, and listeners at a visible boundary. Pair acquisition with cleanup in `finally` or the host's supported resource-management construct. Feature-check runtime support rather than introducing new resource syntax based on recency.

## Preserve errors and `finally`

Catch only when the layer can recover, translate to its contract, add durable context, or guarantee cleanup. JavaScript can throw any value, so do not assume every caught value is an `Error`.

```js
async function loadOrder(id) {
  try {
    return await repository.load(id)
  } catch (error) {
    throw new OrderLoadError(`Could not load order ${id}`, { cause: error })
  }
}
```

Keep `return await` inside this `try` when rejection must be translated here. Returning the promise directly can move its rejection outside the catch. Verify target support before using `Error` options; otherwise preserve context through the project's established mechanism.

Keep protected regions narrow. Avoid logging and rethrowing at every layer, broad fallback values that turn failure into ambiguous success, and `return`/`throw` in `finally` that masks a pending result or error. If cleanup can fail, decide explicitly which error owns the contract.

## Make async policy explicit

Calling an async function starts synchronously until its first suspension and always returns a promise. Adding or removing `async`, wrapping with `Promise.resolve`, or changing callback scheduling can alter synchronous throws, promise identity, and microtask timing.

- Use sequential awaits when ordering, rate limits, locks, transactions, resource pressure, or stop-on-first-completion requires them.
- Use `Promise.all` only to join independent work that is intentionally initiated without awaiting each item; it neither starts promises itself nor cancels unfinished work after one rejects. Preserve where and when each operation is invoked. It preserves result ordering, not start/finish ordering, and changes partial-failure behavior.
- Choose `allSettled`, race/any behavior, bounded concurrency, or explicit rollback only when it matches the domain policy.
- Give every detached promise an explicit error owner. Do not silence it with `void` or an empty catch alone.
- Thread an existing `AbortSignal` through host APIs and collaborators that support it. Cancellation is cooperative; define who creates, combines, observes, and disposes signals/listeners.

Do not convert callbacks or events into one promise when the source can emit repeatedly, signal progress, require unsubscribe, or complete and error independently.

## Keep module boundaries stable

CommonJS and ESM differ in resolution, loading, cycles, evaluation, bindings, interop, and available globals. File extension, nearest package `type`, package `exports`, conditions, and the invoking loader all affect interpretation.

Do not mechanically convert `require`/`module.exports` to `import`/`export`. Check:

- Default versus named export shape and live-binding expectations.
- Synchronous loading, top-level await, cycles, initialization order, and cache identity.
- `__dirname`, `__filename`, `require.resolve`, JSON/addon loading, extension rules, and dynamic loading.
- Package entry points, conditional exports, deep imports, tests, mocks, bundlers, and downstream consumers.

Preserve side-effect imports that register plugins, patches, custom elements, handlers, or styles unless their effect is proven obsolete. Keep public package exports narrow and intentional; changing `exports` can block existing deep imports or route different code to hosts.

## Serialization and host boundaries

JSON is not a general clone or object transport. Preserve omitted `undefined` object properties, array conversions, non-finite numbers, key ordering where contractual, custom `toJSON`, BigInt failures, dates, and accepted reviver/replacer behavior. Validate parsed data before trusting it.

Put dependency seams around host I/O—clock, randomness, environment, storage, network, filesystem, process, DOM—not around every pure function. Inject the smallest useful capability or established client. Keep browser, worker, Node, and edge-only imports behind the correct build/runtime boundary.

## Optimize from evidence

Measure representative workloads before adding caches, concurrency, eager materialization, typed arrays, worker transfers, or mutation-heavy fast paths. Prefer algorithm, I/O/query count, batching, and allocation improvements over syntax folklore. Preserve cache identity/privacy, ordering, backpressure, and memory ceilings.

## Mechanical transformations to reject

Do not perform these without explicit semantic, host, and compatibility checks:

- `==` to `===`, `||` to `??`, or ordinary function to/from arrow.
- Extracting receiver-dependent methods or recreating listener callbacks during removal.
- Substituting object spread, `Object.assign`, JSON cloning, and `structuredClone`.
- Class/prototype instance to plain object, or `Map` to object.
- Loop to array chain, iterable to array, or eager to lazy iteration.
- Sync to async, sequential awaits to/from `Promise.all`, or removing `return await` inside `try`/`catch`/`finally`.
- Callback/event source to a single promise.
- CommonJS to ESM, removing side-effect imports, or changing package exports.

## Verification

Use project-local commands and every supported host/version where practical:

1. Run configured formatting/lint checks, but do not treat them as semantic proof.
2. Run targeted tests, then broader tests for shared, exported, or module-boundary code.
3. Exercise nullish/falsy/absent values, coercion, getters/proxies, receiver and callback identity, aliases, sparse arrays, and iterator cleanup where affected.
4. Check expected error/rejection type, cause, timing, cleanup, cancellation, and unhandled rejection behavior.
5. Test sequential/concurrent start and settlement order plus partial failures when async flow changed.
6. Import/require affected entry points in fresh processes or host contexts; test public exports, cycles, initialization effects, and package conditions.
7. Compare JSON/wire/storage output and read old fixtures when serialization changed.
8. Run production builds for every applicable browser/Node/worker/edge target and inspect for host-only leakage.
9. Measure realistic inputs when claiming performance improvement.

If a host or service is unavailable, run the strongest local subset and name the unverified path.

## JavaScript completion checklist

- Supported hosts, versions, transforms, module formats, and public exports remain compatible.
- Evaluation, coercion, nullish/falsy/absence, receiver, closure, and function identity semantics remain deliberate.
- Prototypes, descriptors, symbols, accessors, aliases, copying, and collection key behavior did not drift.
- Iteration preserves order, laziness/eagerness, sparse behavior, closing, and resource lifetime.
- Error translation is narrow; cause, `finally`, rejection timing, and cleanup remain owned.
- Concurrency, microtask timing, cancellation, and detached work have explicit policies.
- Module initialization, cycles, live exports, side effects, and package resolution remain stable.
- JSON and untrusted object boundaries preserve compatibility and resist prototype pollution.
- Classes, wrappers, options objects, collection choices, and dependency seams earn their cost.
- Performance changes are measured and project-local checks pass across the relevant matrix.

## Primary guidance

Use documentation matching the project's supported hosts:

- [ECMAScript language specification](https://tc39.es/ecma262/)
- [MDN JavaScript Guide](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide)
- [MDN: Functions](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions), [`this`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/this), and [closures](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Closures)
- [MDN: Iteration protocols](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Iteration_protocols) and [promises](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Using_promises)
- [MDN: JavaScript modules](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules), [property ownership/enumerability](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Enumerability_and_ownership_of_properties), and [structured clone](https://developer.mozilla.org/en-US/docs/Web/API/Window/structuredClone)
- [MDN: JSON](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON) and [prototype pollution](https://developer.mozilla.org/en-US/docs/Web/Security/Attacks/Prototype_pollution)
- [Node.js: Packages](https://nodejs.org/api/packages.html), [ECMAScript modules](https://nodejs.org/api/esm.html), and [CommonJS modules](https://nodejs.org/api/modules.html)
