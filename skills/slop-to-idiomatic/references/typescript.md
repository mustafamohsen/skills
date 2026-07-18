# Idiomatic TypeScript

Use this reference for `.ts` and `.tsx` code. It targets design choices that formatters and linters cannot make: trustworthy boundaries, useful domain types, inference, control flow, failure semantics, and abstraction cost.

## Preserve JavaScript behavior first

TypeScript types are erased. A “type cleanup” can still change runtime behavior through new defaults, coercion, validation, property enumeration, imports with side effects, class fields, or changed evaluation order.

Before editing, determine:

- The supported TypeScript version, runtime, module system, target, and strictness flags.
- Whether emitted output, declaration files, or public inferred types are part of the contract.
- Which inputs cross untyped boundaries: network, storage, environment, JSON, DOM, third-party libraries.
- Whether `null`, `undefined`, absence, empty string, and zero have distinct meanings.

Do not enable stricter compiler options as incidental cleanup. Recommend them separately or migrate them in a bounded change with measured fallout.

## Let types prove facts; validate values at boundaries

### Treat untrusted input as `unknown`

Parse or validate once at the edge, then pass a trustworthy domain type inward. A type assertion is not validation.

```ts
type User = { id: string; email: string }

function isUser(value: unknown): value is User {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return typeof candidate.id === 'string' && typeof candidate.email === 'string'
}

function parseUser(value: unknown): User {
  if (!isUser(value)) throw new TypeError('Invalid user payload')
  return value
}
```

Prefer the repository's established schema library when one exists. Keep validation errors and accepted coercions compatible with the existing boundary.

Use `any` only at a genuinely untyped integration seam, document why, and narrow it immediately. Do not spread `any` through internal APIs to silence friction.

### Model domain states directly

Replace correlated flags and optional fields with discriminated unions when callers otherwise can create impossible states.

```ts
// Avoid: data may exist while loading or error may coexist with success.
type LoadState<T> = {
  loading: boolean
  data?: T
  error?: Error
}

type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error }
```

Do not convert every object into a union. Use it where variants have different valid data or behavior.

Distinguish optionality deliberately:

- `field?: T`: the property may be absent; under some configurations it may also accept explicit `undefined`.
- `field: T | undefined`: the key exists but its value may be missing.
- `field: T | null`: explicit empty value, often from a wire or database contract.

Never normalize between these forms without checking serialization, object spread, equality, and API expectations.

Use branded/opaque types only when mixing structurally identical values is a recurring correctness risk and the codebase supports a safe constructor. Avoid casts that let callers manufacture the brand.

### Prefer structural capability over oversized shapes

Accept the smallest meaningful input shape when it improves reuse without hiding domain meaning.

```ts
type Named = { name: string }

function displayName(value: Named): string {
  return value.name.trim()
}
```

Do not create one-property interfaces merely to appear abstract. A named shape should communicate a stable concept or boundary.

## Use inference as a local tool, annotations as contracts

- Let local variables and obvious private returns infer naturally.
- Annotate exported functions and public callbacks when the signature is an intentional API or declaration stability matters.
- Annotate at boundaries to prevent accidental widening or leaking implementation types.
- Use `satisfies` to check a value against a shape while retaining its useful inferred literals.
- Use `as const` only when literal/readonly inference is semantically useful, not as punctuation.

```ts
const routes = {
  home: '/',
  settings: '/settings',
} satisfies Record<string, `/${string}`>
```

Avoid redundant type annotations that restate the initializer and make refactors noisier.

### Assertions are proof obligations

Before keeping `as T`, `!`, or a double assertion, identify the runtime fact that makes it safe. Prefer, in order:

1. Control-flow narrowing.
2. A boundary validator or assertion function.
3. A more accurate source type.
4. A localized assertion with an invariant comment when the compiler cannot express a proven fact.

Never add `as unknown as T` to complete a refactor. Non-null assertions are especially risky after lookup, DOM query, parsing, or async work.

Use exhaustive checking for closed unions:

```ts
function assertNever(value: never): never {
  throw new Error(`Unhandled variant: ${String(value)}`)
}

function label(state: LoadState<unknown>): string {
  switch (state.status) {
    case 'idle': return 'Idle'
    case 'loading': return 'Loading'
    case 'success': return 'Ready'
    case 'error': return state.error.message
    default: return assertNever(state)
  }
}
```

Preserve the prior fallback behavior if the value actually comes from an open or untrusted source.

## Design functions around real variation

### Generics must preserve a relationship

A generic is useful when the same type relationship connects inputs and outputs or constrains related inputs.

```ts
function first<T>(values: readonly T[]): T | undefined {
  return values[0]
}
```

Avoid generic parameters used once, unconstrained “flexibility,” and helpers whose body must cast the generic back to a concrete type. Prefer a concrete type, union, or established interface when there is no relationship to preserve.

Use overloads only when callers receive materially different types from distinct call shapes and one union signature would lose that relationship. Keep the implementation signature honest and test all overload paths.

### Keep parameter lists meaningful

- Use positional arguments for a few obvious, stable values.
- Use an options object when arguments are numerous, optional, easy to swap, or expected to evolve.
- Do not wrap a single obvious parameter in an options object without a local convention or evolution need.
- Preserve callback variance and `this` behavior when converting methods or arrow functions.

Prefer pure transformations for domain logic, but do not turn readable mutation in a local accumulator into a dense `reduce`. Use the construct that exposes intent:

- `map` for one output per input.
- `filter` for retaining items.
- `find`/`some`/`every` for early-exit queries.
- A loop for multiple accumulators, branching, early continuation, or clearer mutation.
- `Map`/`Set` when key identity, uniqueness, or repeated lookup is the actual model—not merely because they seem sophisticated.

## Make control flow explicit

- Prefer guard clauses when they remove nesting and leave the main path visible.
- Keep related conditions together; do not scatter one invariant across distant early returns.
- Use `??` for missing values and `||` for falsy values only when `false`, `0`, and `''` should trigger the fallback.
- Use optional chaining for genuinely optional traversal, not to silently turn invariant violations into `undefined`.
- Name complex predicates when the name adds domain meaning.
- Avoid nested ternaries for multi-branch business logic.

Generated code often introduces `async` wrappers that only return another promise. Remove them only after checking stack traces, `try/catch/finally`, promise identity, and synchronous-throw conversion.

## Preserve failure semantics

Catch only when the current layer can add context, translate to its own contract, recover, or guarantee cleanup.

```ts
try {
  return await repository.load(id)
} catch (error: unknown) {
  throw new OrderLoadError(id, { cause: error })
}
```

- Narrow caught values; JavaScript can throw anything.
- Preserve `cause` when wrapping errors if supported by the target.
- Do not log and rethrow at every layer; choose an ownership point for logging.
- Do not replace errors with `null`, empty arrays, or `{ success: false }` unless that is the established contract.
- Use a result/discriminated-union return when failure is an expected domain outcome callers must handle, not as a blanket ban on exceptions.
- Keep programmer errors distinct from user/input failures.

## Respect async and resource semantics

- Use `Promise.all` only for independent work that may run concurrently; it preserves result order but changes start timing and failure behavior.
- Keep sequential awaits when order, rate limits, locks, transactions, or resource pressure require them.
- Thread `AbortSignal` through cancellable I/O when the surrounding API supports cancellation.
- Never leave floating promises unless intentionally detached with explicit error ownership.
- Preserve cleanup in `finally`; do not let cleanup errors accidentally mask primary errors without deciding that policy.
- Beware stale results when multiple requests race; ownership belongs at the caller or framework layer that knows which result is current.

## Keep modules predictable

- Organize by cohesive feature/domain when that matches the project; avoid `utils.ts` dumping grounds.
- Keep side effects out of import-time code unless module initialization is the documented contract.
- Prefer direct imports when barrel files cause cycles, hide boundaries, or inflate bundles. Keep established public barrels stable.
- Use type-only imports when required by the compiler/module configuration and when they clarify runtime dependencies.
- Avoid duplicate “DTO,” “model,” and “entity” types that are structurally identical unless each marks a real boundary with different evolution rules.
- Prefer functions and plain objects for data/operations. Use classes when identity, encapsulated invariants, lifecycle, polymorphism, or framework integration makes them earn their weight.

Naming should expose domain intent. Avoid generated placeholders such as `data`, `result`, `item`, `processData`, `handleThing`, `Manager`, `Helper`, and `Service` when a more precise role is known. Do not rename stable public APIs for taste alone.

## Common refactors

### Remove exception-driven optional lookup

```ts
// Before
function getName(users: User[], id: string): string {
  try {
    return users.filter((user) => user.id === id)[0].email
  } catch {
    return ''
  }
}

// After, if empty string is the established not-found contract
function getName(users: readonly User[], id: string): string {
  return users.find((user) => user.id === id)?.email ?? ''
}
```

This is safe only after confirming the old catch did not intentionally absorb getter/proxy failures too.

### Replace boolean mode arguments with intent

```ts
// Before
save(order, true, false)

// After
save(order, { validate: true, notifyCustomer: false })
```

Do this when call-site ambiguity is real and the API migration is within scope. For two stable internal callers, two named functions may communicate intent better than a growing options bag.

### Delete pass-through abstraction

```ts
// Before
class UserService {
  constructor(private readonly repository: UserRepository) {}
  getUser(id: string) { return this.repository.getUser(id) }
}

// After: inject/use UserRepository directly, unless UserService is a deliberate boundary
```

Check tests, dependency injection, transaction boundaries, authorization, and future API compatibility before deleting the layer.

## TypeScript completion checklist

- Untrusted values are validated/narrowed once, not asserted repeatedly.
- Domain variants prevent meaningful impossible states.
- Null, undefined, absent, empty, and falsy semantics remain correct.
- Generics and overloads encode real relationships.
- Public types and declaration output did not drift accidentally.
- Async ordering, cancellation, and error ownership remain deliberate.
- Imports do not introduce cycles, side effects, or client bundle leakage.
- Suppressions and assertions are fewer or better justified.
- The implementation uses straightforward JavaScript constructs with TypeScript adding guarantees, not ceremony.

## Primary guidance

- [TypeScript Handbook: The Basics](https://www.typescriptlang.org/docs/handbook/2/basic-types.html)
- [TypeScript Handbook: Narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
- [TypeScript Handbook: Generics](https://www.typescriptlang.org/docs/handbook/2/generics.html)
- [TypeScript TSConfig reference](https://www.typescriptlang.org/tsconfig/)
