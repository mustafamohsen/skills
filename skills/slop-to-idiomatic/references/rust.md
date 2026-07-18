# Idiomatic Rust

Use this reference for Rust code. Idiomatic Rust makes ownership, invalid states, failure, concurrency, and cost visible in the API. Passing `rustfmt` and Clippy is necessary evidence, not the design goal.

## Establish the crate contract

Before editing, inspect:

- `Cargo.toml`, workspace inheritance, crate type, features, and target platforms.
- Rust edition, toolchain pin, minimum supported Rust version (MSRV), `no_std`/`alloc`, and unsafe policy.
- Public API exposure through `pub`, re-exports, doctests, examples, and downstream workspace crates.
- Async runtime, serialization formats, FFI, persistence, and feature-gated behavior.
- Whether allocation count, binary size, latency, or zero-copy behavior matters in the scoped path.

Do not introduce APIs newer than the MSRV or change feature unification/default features incidentally. A public signature refactor can be semver-breaking even if every in-repository caller compiles.

## Let ownership describe responsibility

Choose parameter and return ownership from what the function needs:

- Borrow with `&T` when reading an existing value.
- Borrow with `&mut T` when mutating in place is the operation's purpose.
- Take `T` when consuming, storing, transforming ownership, or moving across a task/thread boundary.
- Prefer `&str` over `&String` and `&[T]` over `&Vec<T>` for read-only inputs.
- Return owned values when creating them. Do not add output lifetimes to avoid a justified allocation.
- Use `Cow<'a, T>` only when callers materially benefit from sometimes-borrowed, sometimes-owned output; it is not a default optimization.

Do not clone to appease the borrow checker before understanding who should own the value. Equally, do not contort simple code with difficult lifetimes to eliminate an allocation that is cheap and off the hot path.

```rust
// Avoid: requires a Vec and clones every value.
fn normalized(values: &Vec<String>) -> Vec<String> {
    values.iter().map(|value| value.trim().to_owned()).collect()
}

// Prefer: accepts any slice; allocation is explicit in the result contract.
fn normalized(values: &[String]) -> Vec<String> {
    values.iter().map(|value| value.trim().to_owned()).collect()
}
```

Moving an input instead of cloning it may change whether the caller can reuse it. Changing a return from owned to borrowed may couple lifetimes and reduce usability. Treat both as API changes, not automatic wins.

### Shared ownership and interior mutability are deliberate

- Use `Rc<T>` for shared ownership in one thread and `Arc<T>` across threads only when ownership is genuinely shared.
- Use `Cell`/`RefCell` or locks when mutation through shared references is the domain model, not as a first response to borrow errors.
- Keep lock scope small and obvious. Avoid holding a synchronous lock guard across `.await`.
- Do not wrap every service in `Arc<Mutex<_>>`; prefer owned task state, message passing, atomics, or narrower synchronization when those match the behavior.
- Be alert to `Rc`/`Arc` cycles; use `Weak` for non-owning back-references.

## Model invariants in types

### Use enums for alternatives, structs for simultaneous facts

Replace tag strings, sentinel numbers, and correlated options with enums when the set is closed.

```rust
// Avoid: callers can construct contradictory combinations.
struct JobState {
    running: bool,
    output: Option<String>,
    error: Option<String>,
}

enum JobState {
    Pending,
    Running,
    Complete { output: String },
    Failed { error: JobError },
}
```

Match exhaustively inside the owning crate. Consider `#[non_exhaustive]` only for public enums/structs that truly need compatible future variants; it imposes real costs on downstream construction and matching.

Use newtypes when they enforce a domain distinction, invariant, unit, or trait boundary:

```rust
struct UserId(String);

impl UserId {
    fn parse(value: impl Into<String>) -> Result<Self, InvalidUserId> {
        let value = value.into();
        if value.is_empty() { return Err(InvalidUserId); }
        Ok(Self(value))
    }
}
```

Keep fields private when construction must preserve an invariant. Do not add dozens of transparent newtypes with unchecked `.0` access and no safety or domain benefit.

### Use `Option` and `Result` for their real meanings

- `Option<T>` means absence is expected and has one useful dimension.
- `Result<T, E>` means the operation can fail and callers need the reason.
- An empty collection is often better than `Option<Vec<T>>` when “no elements” and “not available” are not distinct.
- Do not use magic values (`-1`, empty string, all-zero ID) for absence.
- Do not convert a meaningful error to `None` with `.ok()` unless loss of the reason is the explicit contract.

Make invalid construction fail at the boundary, then let internal code rely on the validated type.

## Design APIs that compose with the ecosystem

Follow standard naming and conversion expectations:

- `new` constructs; `default` supplies a sensible default.
- `as_` is cheap borrowed-to-borrowed, `to_` is potentially allocating/expensive, `into_` consumes.
- Collections expose `iter`, `iter_mut`, and `into_iter` consistently.
- Use `From`/`Into` for infallible conversions and `TryFrom`/`TryInto` for fallible ones.
- Use `AsRef`/`AsMut` for cheap reference conversion in generic APIs. Use `Borrow` only when its equality/hash equivalence contract is required.
- Getters normally use the field/concept name (`name()`), not `get_name()`.
- Constructors with many easy-to-confuse options may use a validated options struct or builder; do not create builders for trivial types.

Derive or implement common traits when their semantics are honest and useful: `Debug`, `Clone`, `Copy`, `Default`, `Eq`, `Ord`, `Hash`. Do not derive `Copy` merely for convenience on a type whose identity or future evolution suggests moves should remain visible.

Mark important returned values `#[must_use]` when ignoring them is almost certainly a bug. Avoid annotating every getter and flooding users with noise.

### Public types should be usable, not just compilable

- Accept flexible borrowed inputs where it improves call sites without generic bloat.
- Return concrete types unless abstraction is part of the contract.
- Prefer `impl Iterator`/`impl Trait` when callers need behavior but not the concrete type and hidden type stability is acceptable.
- Use `dyn Trait` when runtime heterogeneity or plugin boundaries require dynamic dispatch.
- Use generics when static dispatch and caller-selected types provide real value.
- Keep trait bounds at the narrowest surface that needs them.

Do not create traits for a single implementation solely to enable mocking. First consider testing through a real lightweight collaborator, a function/closure parameter, or a small boundary trait owned by the consumer.

## Keep lifetimes descriptive

Rely on lifetime elision when the relationship is unambiguous. Add named lifetimes to express a relationship between borrows, not to make the compiler quiet.

If lifetime annotations become pervasive, reconsider ownership:

- Should the result own its data?
- Is a struct borrowing data longer than useful?
- Can work happen in one scope instead of storing references?
- Is an arena or interned representation an established project design rather than a local workaround?

Avoid self-referential structures and leaked allocations unless the architecture explicitly calls for them and the safety/lifecycle story is documented.

## Use iterators and control flow for clarity

Iterator chains are idiomatic when each stage has one clear meaning. A loop is idiomatic when it makes branching, early exit, mutation, error context, or multiple outputs clearer.

```rust
let active_names: Vec<_> = users
    .iter()
    .filter(|user| user.is_active())
    .map(|user| user.name.as_str())
    .collect();
```

Avoid dense chains with nested closures, side effects, and several `filter_map` conversions that hide failure. Name intermediate concepts or use a loop.

Use combinators when they preserve the obvious shape:

- `map` transforms a contained success/value.
- `and_then` chains a fallible/optional operation.
- `ok_or`/`ok_or_else` turns expected absence into an error.
- `collect::<Result<Vec<_>, _>>()` stops at the first error while collecting.

Use `if let`/`let else` for one interesting pattern, `while let` for repeated matching, and `match` when alternatives carry domain meaning. Do not replace an exhaustive domain match with clever boolean expressions.

### Use collection entry APIs

Avoid duplicate lookups or awkward contains-then-insert flows when `entry` expresses one operation:

```rust
counts.entry(word).and_modify(|count| *count += 1).or_insert(1);
```

Choose `Vec`, `VecDeque`, `HashMap`, `BTreeMap`, `HashSet`, and ordered/indexed alternatives from actual access, ordering, hashing, and determinism needs. Changing collection type can change output order and serialization.

## Preserve error meaning and context

Use `?` to propagate errors through compatible boundaries. Add context where the current layer knows what operation or identifier failed.

- Libraries usually expose a stable, structured error type callers can inspect.
- Applications may use an erased/contextual error type when callers only report or terminate, if that is the project's established approach.
- Preserve sources when wrapping errors.
- Keep user/input errors separate from internal invariant failures.
- Avoid one giant error enum that couples unrelated modules.
- Avoid converting every error to a formatted `String`; it loses source chains and machine handling.

`panic!`, `unwrap`, and `expect` are for violated programmer invariants, tests/examples, process startup that cannot continue, or conditions proven locally. For `expect`, state the invariant (“validated non-empty above”), not a generic failure (“should work”).

Do not replace existing recoverable errors with panics during cleanup. Do not mechanically eliminate every `unwrap` when the invariant is structurally guaranteed; make the proof visible or improve the type.

## Respect async and concurrency semantics

- Use the runtime already selected by the project; do not mix runtimes casually.
- Do not mark functions async without awaiting or returning asynchronous work for a trait/API reason.
- Preserve ordering and backpressure when replacing loops with concurrent joins/streams.
- Bound concurrency for untrusted or large input sets.
- Keep cancellation safety in mind: an async operation may be dropped at any await point.
- Ensure spawned tasks have explicit ownership, error reporting, and shutdown behavior; detached tasks are not free.
- Avoid blocking filesystem/network/CPU work on an async executor thread; use the runtime's blocking boundary when needed.
- Do not hold borrow guards or mutex guards across `.await` unless the primitive and design are specifically async-safe and contention is understood.
- Prefer channels when a task naturally owns mutable state; prefer shared locks when many readers/writers truly share it.

Adding `Send + Sync + 'static` bounds “just in case” overconstrains APIs. Add only what the execution boundary requires.

## Keep modules and visibility intentional

- Organize modules around domain capabilities, not one type per file by default.
- Default to private; use `pub(crate)` for workspace-internal surfaces and `pub` for deliberate external API.
- Re-export a coherent public facade. Avoid wildcard re-export trees that obscure ownership and create name collisions.
- Keep feature-gated modules and public items consistent across supported feature combinations.
- Avoid `mod utils` dumping grounds; give helpers the domain concept they serve.
- Document public invariants, errors, panics, safety requirements, and meaningful examples.

Do not move code only to shorten files. Extract when the new module has a cohesive responsibility and sensible visibility.

## Unsafe and FFI require a proof

Do not introduce `unsafe` as a refactor shortcut. For existing unsafe code:

- Minimize the unsafe block and expose a safe API.
- State the safety invariants immediately at the block or function.
- Verify aliasing, initialization, validity, alignment, provenance, lifetimes, unwind behavior, and thread safety as applicable.
- Preserve `unsafe fn` caller obligations and FFI ABI/layout contracts.
- Use tested standard-library safe abstractions when they express the operation.

Run Miri or sanitizer/FFI-specific checks when available and proportionate. Clippy cannot prove an unsafe block sound.

## Avoid performance folklore

- Measure hot paths before adding complex borrowing, pooling, unsafe code, or custom collections.
- Remove obviously unnecessary clones/allocations only after checking ownership and API consequences.
- Prefer borrowing and iterator adapters that compile to straightforward code, but optimize for readable invariants first.
- Be careful with `format!`, repeated string concatenation, regex compilation, and collection reallocation inside hot loops.
- Use capacity hints when size is known and allocation matters, not everywhere.
- Preserve deterministic ordering when tests, wire output, hashing, or users depend on it.

## Common refactors

### Replace manual option branching with a typed conversion

```rust
// Before
let user = match users.get(&id) {
    Some(user) => user,
    None => return Err(AppError::NotFound(id.clone())),
};

// After
let user = users
    .get(&id)
    .ok_or_else(|| AppError::NotFound(id.clone()))?;
```

The explicit match may still be clearer when branches add multiple steps or distinct context.

### Remove a defensive clone by moving at the ownership boundary

```rust
// Before
fn enqueue(queue: &mut Vec<Job>, job: &Job) {
    queue.push(job.clone());
}

// After, if the caller should transfer ownership
fn enqueue(queue: &mut Vec<Job>, job: Job) {
    queue.push(job);
}
```

Update callers only when losing access to `job` matches the domain operation.

### Replace stringly dispatch with an enum

Parse external strings once with `FromStr`/`TryFrom`, return the established parse error, and match on the enum internally. Preserve casing, aliases, unknown-value policy, and serialized representation.

## Verification

Use project-local commands. A typical risk-ordered set is:

1. `cargo fmt --check`
2. `cargo check` for relevant packages, targets, and feature sets
3. Targeted `cargo test`
4. Workspace/all-target tests when shared APIs changed
5. `cargo clippy` with the repository's configured lint policy
6. `cargo doc`/doctests for public APIs
7. Miri, sanitizer, loom, benchmarks, or cross-target checks when the changed code warrants them

Do not blindly use `--all-features` if features are intentionally mutually exclusive. Test the supported matrix.

## Rust completion checklist

- Ownership transfer, borrowing, cloning, and allocation match real responsibility.
- Enums/newtypes/visibility encode valuable invariants without ceremony.
- `Option`, `Result`, panics, and error context retain their intended meanings.
- Public APIs follow standard names, conversions, traits, and MSRV constraints.
- Iterator/control-flow choices expose rather than compress intent.
- Async work has bounded concurrency, cancellation, error, and shutdown ownership.
- Locks and shared ownership are no broader than required.
- Unsafe invariants remain explicit and verified.
- Feature combinations, serialization, ordering, and downstream APIs remain compatible.

## Primary guidance

- [The Rust Programming Language](https://doc.rust-lang.org/book/)
- [Rust standard library API conventions](https://doc.rust-lang.org/std/)
- [Rust API Guidelines checklist](https://rust-lang.github.io/api-guidelines/checklist.html)
- [The Clippy Book](https://doc.rust-lang.org/clippy/)
- [The Rustonomicon](https://doc.rust-lang.org/nomicon/)
