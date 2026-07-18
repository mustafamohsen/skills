# Idiomatic C++

Use this reference for C++ source, headers, tests, and build-facing API changes. Determine whether ambiguous `.h` files are C or C++ from their build targets and consumers; never apply C++ guidance by extension alone. Idiomatic C++ makes ownership, lifetime, invariants, failure, concurrency, and cost visible while respecting the repository's language level and compatibility obligations. Passing a formatter and warning-clean compilation is evidence, not the design goal.

## Establish the C++ contract

Before editing, inspect:

- The required C++ standard, compiler and standard-library versions, target platforms, and supported build configurations.
- The build system, target boundaries, compile database when available, compile definitions/options, generated sources, package manager, and test commands.
- Public headers, exported symbols, calling conventions, binary consumers, plugin/FFI boundaries, and ABI policy.
- Exception and RTTI settings, allocator strategy, sanitizer support, warning policy, and static-analysis configuration.
- Threading model, ownership conventions, real-time or embedded constraints, and whether allocation, latency, code size, or determinism matters.
- Repository conventions for naming, formatting, include order, header guards, smart pointers, error types, and test doubles.

This reference assumes no minimum dialect. Treat every facility in its examples as version-gated: `std::exchange` and `std::make_unique` require C++14; `std::byte`, `std::string_view`, `std::optional`, `std::variant`, `[[nodiscard]]`, and `std::scoped_lock` require C++17; `std::span`, ranges, concepts, `std::jthread`, and stop tokens require C++20; `std::expected` requires C++23. Library availability may lag the language mode, so verify the actual toolchain rather than relying only on `__cplusplus`.

Do not introduce a newer language or library facility into an older target, require a newer standard library accidentally, or “modernize” a public signature without checking source, binary, and behavioral compatibility. Build at least the affected supported configuration; debug-only success does not establish release correctness.

## Preserve more than output values

A C++ refactor can change behavior through object lifetime, overload resolution, implicit conversions, evaluation order, temporary materialization, iterator invalidation, allocation, exceptions, locking, or undefined behavior.

Add applicable items to the preservation ledger:

- Object layout, alignment, vtables, exported names, inline definitions, and C/FFI representation.
- Copy/move availability, triviality, `noexcept`, destruction order, and moved-from guarantees.
- Reference, pointer, iterator, view, and callback lifetimes.
- Container ordering, iterator/reference stability, hash behavior, and allocation patterns.
- Exception type, message when contractual, exception-safety guarantee, and termination behavior.
- Lock acquisition order, memory ordering, thread affinity, cancellation, and shutdown.
- Macro values, feature gates, compile-time evaluation, and platform-specific branches.

Undefined behavior is not a behavior-preservation target. If the existing path depends on a dangling reference, race, invalid cast, uninitialized value, signed overflow, or other undefined behavior, classify it as a correctness defect. Fix it only within the approved scope, lock the intended behavior down with a focused test or sanitizer reproducer, and report the correction separately from behavior-neutral cleanup.

## Make ownership and lifetime explicit

### Prefer RAII for every resource

Represent resource ownership with an object whose destructor releases it. This applies to memory, files, sockets, locks, transactions, registrations, and platform handles.

- Prefer values and standard containers to manual allocation.
- Prefer automatic storage when scope is the lifetime.
- Use `std::unique_ptr<T>` for exclusive heap ownership.
- Use `std::shared_ptr<T>` only when ownership is genuinely shared; use `std::weak_ptr<T>` for non-owning links that must observe shared lifetime or break cycles.
- Use a focused RAII wrapper with the correct deleter for C or OS resources.
- Do not encode ownership in a raw pointer unless a fixed external API requires it and the contract is documented.
- Prefer factory helpers such as `std::make_unique`; use direct construction when a custom deleter, allocation strategy, or access rule requires it.

```cpp
class File {
public:
    explicit File(std::FILE* handle) : handle_(handle) {
        if (handle_ == nullptr) {
            throw std::invalid_argument("File requires a valid handle");
        }
    }

    ~File() {
        if (handle_ != nullptr) std::fclose(handle_);
    }

    File(const File&) = delete;
    File& operator=(const File&) = delete;

    File(File&& other) noexcept : handle_(std::exchange(other.handle_, nullptr)) {}
    File& operator=(File&& other) noexcept {
        if (this != &other) {
            if (handle_ != nullptr) std::fclose(handle_);
            handle_ = std::exchange(other.handle_, nullptr);
        }
        return *this;
    }

private:
    std::FILE* handle_;
};
```

Prefer an established project wrapper or a `unique_ptr` with a deleter over writing a new resource class when either already expresses the contract.

### Treat non-owning types as lifetime promises

A reference, raw pointer, iterator, `std::span`, `std::string_view`, ranges view, and lambda reference capture does not extend lifetime.

- Use `T&` for a required existing object and `T*` for optional/reseatable observation when that matches local conventions.
- Use `std::span<T>` for a non-owning contiguous sequence when C++20 is available and the caller must retain storage.
- Use `std::string_view` for synchronous observation, not stored ownership. Do not return or retain a view into a temporary or invalidated string.
- Check iterator, pointer, and reference invalidation before changing a container or inserting/erasing elements.
- Capture lambdas deliberately. Avoid `[&]` or `[=]` when callbacks escape the current scope; make object and lifetime ownership visible.
- Be especially careful when work crosses a thread, coroutine, event loop, or deferred callback boundary.

Do not replace an owning `std::string` with `std::string_view` merely to avoid a copy. The apparent optimization can introduce lifetime coupling and make the API harder to use safely.

## Design value types with the Rule of Zero

Prefer members whose own types correctly manage their resources so the enclosing type needs no custom destructor, copy, or move operations.

```cpp
struct Customer {
    CustomerId id;
    std::string name;
    std::vector<Order> orders;
};
```

When a type must define one special member, review all five operations: destructor, copy constructor, copy assignment, move constructor, and move assignment. Decide whether the type is copyable, move-only, immovable, or value-like; do not let accidental suppression or generation decide the API.

- Use `= default` to state intended default semantics and `= delete` to prohibit an operation.
- Preserve whether operations are trivial, `constexpr`, accessible, and `noexcept` when those properties affect containers, ABI, or callers.
- Keep moved-from objects valid and destructible; promise a stronger state only when the API documents and tests it.
- Remember that `std::move` is a cast enabling move overload resolution; it does not move by itself.
- Do not `std::move` a local return value reflexively; it can inhibit copy elision and obscure intent.

## Shape interfaces around ownership and use

Choose parameter forms from the operation's semantics, not a universal style rule:

- Pass small, cheap value-like inputs by value.
- Pass a read-only object by `const T&` when copying is not intended or cheap.
- Pass `T&` when the function mutates a caller-owned object.
- Pass `T` to a sink that takes ownership; move it into stored state.
- Use `T&&` for an explicit consuming/rvalue overload or forwarding reference only when its semantics are understood.
- Use pointer/span/view forms only when nullability, sequence observation, or lifetime coupling is part of the contract.

Returning by value is normally the clear ownership boundary; rely on copy elision and move semantics. Return a reference or view only when the referent's lifetime and invalidation rules are obvious and useful to callers.

Keep APIs hard to misuse:

- Prefer cohesive types over long parameter lists and boolean mode arguments.
- Use strong domain types when confusing identical primitives is a recurring correctness risk.
- Prefer `enum class` for a closed set of named alternatives, but preserve public underlying values, serialization, and ABI.
- Use `std::optional<T>` for expected absence, `std::variant` for a closed set of alternatives, and a result/error type for expected failure. Do not collapse distinct outcomes into sentinels.
- Apply `[[nodiscard]]` to results whose loss is likely a bug, not to every getter.
- Avoid implicit converting constructors and conversion operators unless implicit conversion is the intended, unsurprising API.

Do not add getters and setters mechanically. A class should protect an invariant or own behavior; otherwise a value type with direct, intentional fields may be clearer.

## Keep polymorphism deliberate

- Prefer composition or value semantics unless substitutable runtime behavior is the real model.
- A base intended for polymorphic deletion needs a public virtual destructor; a base not intended for deletion through it should prevent that use.
- Mark overrides with `override`. Use `final` only when extension is intentionally prohibited or evidence justifies devirtualization.
- Avoid calling virtual functions from constructors and destructors as if they dispatched to a fully derived object.
- Prevent accidental object slicing when passing or storing polymorphic objects.
- Do not create an interface solely because generated code expects every dependency to be mockable. A narrow consumer-owned boundary, value, callable, or real lightweight collaborator may be simpler.

Changing a class hierarchy, virtual member order, virtual destructor, or member layout can break ABI. Treat it as an explicit compatibility change.

## Express invariants with types and initialization

- Initialize every object before use; prefer construction that establishes a valid state.
- Use in-class member initializers for stable defaults and constructor initializer lists for per-construction values.
- Keep declaration order aligned with initialization dependencies; members initialize in declaration order, not initializer-list order.
- Use `nullptr`, not integer null constants.
- Use scoped enums, `std::optional`, `std::variant`, and validated value types where they remove meaningful invalid states.
- Keep representation private when construction or mutation must preserve an invariant.
- Use `const` for objects and member functions that are logically non-mutating. Do not use `mutable` to conceal synchronization or ownership mistakes.
- Use `constexpr`/`consteval` when compile-time evaluation is part of the useful contract and supported by the target—not as decoration.

Choose initialization syntax deliberately. Braces prevent narrowing but can prefer `std::initializer_list` overloads; parentheses can select a different constructor. Verify overload resolution rather than enforcing one punctuation style mechanically.

## Make control flow readable

- Prefer guard clauses when they expose the normal path without scattering one invariant across many exits.
- Use a range-based `for` loop for straightforward traversal and preserve reference/value intent (`const auto&`, `auto&`, or a copy).
- Use standard algorithms or ranges when the operation is naturally a search, transform, partition, sort, or accumulation and the result is clearer than manual indexing.
- Prefer a loop when it better expresses early exits, several accumulators, stateful branching, iterator-sensitive mutation, or error context.
- Avoid `std::for_each` merely to make side-effecting code look functional.
- Use structured bindings carefully. `auto [key, value]` commonly gives value bindings for value-like elements, but tuple-like elements declared as references remain references; `auto&`/`const auto&` binds the hidden object by reference. Verify the initializer and element types instead of assuming copy or observation.
- Use `auto` when the initializer makes the type evident or the exact type is incidental. Spell the type when it communicates ownership, signedness, precision, conversion, or domain meaning.

Preserve algorithm complexity, ordering, and invalidation. Replacing a loop with ranges is not an improvement when it requires a dense pipeline, changes language requirements, or hides mutation and failure.

## Preserve error and exception semantics

Follow the project's established exception policy. Do not introduce exceptions into an exception-disabled target or replace structured failures with status codes merely for taste.

- Use exceptions for failures that cannot be handled locally when that is the codebase contract.
- Use `std::expected<T, E>` only where C++23 support exists and expected failure is part of the API. Use the repository's established result type on older standards.
- Use `std::optional<T>` for absence, not to erase a meaningful reason for failure.
- Catch only where the layer can recover, translate to its contract, add durable context, or enforce a boundary.
- Catch by reference. Preserve the dynamic exception when rethrowing with `throw;`; `throw error;` can slice or reset information.
- Do not let destructors emit exceptions during stack unwinding.
- Make the basic, strong, or no-throw exception guarantee intentional for mutating operations. Prefer committing state only after fallible preparation succeeds.
- Add `noexcept` only when the function cannot escape with an exception and termination is the desired fallback. Changing `noexcept` can affect ABI, overloads, containers, and failure behavior.

Assertions document programmer invariants, not recoverable input errors. Preserve build-mode differences: `assert` commonly disappears under `NDEBUG` and must not contain required side effects.

## Use templates and concepts only for real variation

- Prefer a concrete function when the operation has one meaningful type.
- Use templates when callers select types and the implementation preserves a useful relationship across them.
- Constrain templates with C++20 concepts or the project's established mechanism so diagnostics and valid operations match the contract.
- Keep constraints semantic; “has these expressions” is not enough when algorithms require equality, ordering, ownership, or lifetime laws.
- Put only necessary template definitions in headers and watch compile time, code size, and ABI exposure.
- Use forwarding references with `std::forward` only for genuine forwarding layers. Do not add universal-reference overloads that steal calls from clearer overloads.
- Prefer standard customization mechanisms and ordinary overloads over macro-generated or metaprogramming-heavy dispatch.

Do not introduce concepts, tag dispatch, CRTP, type erasure, or template traits to solve a single concrete call site unless they clarify an established extension boundary.

## Keep headers and build boundaries sound

- Keep public headers self-contained and include what their declarations require; do not rely on transitive includes.
- Prefer declarations in headers and non-template definitions in source files when that matches the target and ABI model.
- Do not put `using namespace` directives in headers.
- Avoid macros for constants, functions, and type aliases when language facilities suffice. Keep macros for legitimate preprocessing, platform, and configuration boundaries.
- Respect the One Definition Rule. Use `inline`, internal linkage, unnamed namespaces, and inline variables according to actual linkage needs—not to silence duplicate-symbol errors blindly.
- Preserve symbol visibility/export annotations and C linkage at shared-library and FFI boundaries.
- Use a PImpl only when ABI stability, compile-time isolation, or encapsulation justifies its allocation and indirection.
- Adopt modules only when the repository toolchain and dependency graph already support them; do not mix them into a refactor as a style upgrade.
- Express target usage requirements through the build system's target model rather than global flags when changing build files, but do not redesign the build incidentally.

Never hand-edit generated code unless the generator workflow explicitly requires it. Fix the schema, template, or generator and regenerate reproducibly.

## Treat undefined behavior and casts as high risk

Investigate rather than cosmetically rewriting:

- Uninitialized reads, dangling references, out-of-bounds access, invalid iterator use, and use-after-move assumptions.
- Signed overflow, invalid shifts, division edge cases, strict-aliasing violations, alignment, object lifetime, and union-punning.
- `reinterpret_cast`, C-style casts, `const_cast`, pointer arithmetic, and unchecked downcasts.
- `memcpy`, `memset`, or raw serialization of non-trivially-copyable objects.
- Ownership transferred through `new`/`delete`, `malloc`/`free`, or mismatched allocation families.

Prefer the narrowest named cast when conversion is genuinely required. A `static_cast` can still be wrong; the spelling documents the category, not correctness. Keep low-level operations behind a small safe interface with explicit preconditions and representation tests.

## Preserve concurrency semantics

A data race is undefined behavior. Treat synchronization and task lifetime as part of the API.

- Prefer immutable data, thread confinement, or message passing before shared mutable state when they fit the design.
- Use RAII locks (`std::lock_guard`, `std::unique_lock`, `std::scoped_lock`) and keep critical sections small.
- Define a consistent lock order; use `std::scoped_lock` for coordinated acquisition where appropriate.
- Never add or relax atomic memory orders casually. Use the simplest correct ordering and document non-sequential reasoning.
- Make thread/task ownership, stop signaling, exception handling, and joining explicit. Do not detach work without a process-lifetime ownership design.
- Use `std::jthread`/`std::stop_token` only when the target supports C++20 and cooperative cancellation matches the API.
- Do not hold a lock while invoking unknown callbacks or performing slow/blocking I/O unless the invariant requires it and reentrancy is understood.
- Preserve condition-variable predicates and wait in a predicate loop.

Run ThreadSanitizer where supported for changed concurrent paths, but do not treat one clean run as a proof of race freedom.

## Optimize from evidence

- Prefer clear ownership and suitable data structures before micro-optimizing syntax.
- Measure the relevant build and workload; debug timings and isolated microbenchmarks can mislead.
- Account for algorithmic complexity, cache locality, allocations, copies, contention, and I/O before clever low-level tuning.
- `std::vector` is a strong default sequence when contiguous storage and invalidation rules fit; choose another container from required access, stability, ordering, and allocation behavior.
- Reserve capacity when a useful bound is known and allocation matters, not everywhere.
- Avoid accidental copies in range loops, structured bindings, lambda captures, and parameter passing, while retaining copies that provide necessary ownership.
- Do not replace readable code with views, expression templates, custom allocators, pooling, or manual SIMD without measured benefit and maintainable invariants.

Changing layout, small-buffer behavior, allocation timing, or container type may affect ABI, iterator validity, memory peaks, latency, and deterministic output. Treat those as behavior and performance decisions.

## Common generated-code refactors

### Replace manual ownership with RAII

```cpp
// Before
Widget* widget = new Widget(config);
run(*widget);
delete widget;

// After, if dynamic lifetime is unnecessary
Widget widget{config};
run(widget);
```

If polymorphic or dynamic ownership is required, use `std::unique_ptr` and transfer it explicitly. Confirm destruction timing; moving destruction to scope exit can change observable resource release.

### Replace output parameters with a value result

```cpp
struct ParseResult {
    Header header;
    Payload payload;
};

[[nodiscard]] ParseResult parse_message(std::span<const std::byte> bytes);
```

Do this only when it preserves allocation, failure, and partial-output semantics and the language level supports the chosen view type.

### Replace a boolean mode with a named operation

```cpp
// Before
serialize(record, true);

// After
serialize_compact(record);
```

A small options type may be better when several independent choices are real. Preserve public source/ABI compatibility or migrate it explicitly.

### Remove a redundant abstraction

A one-use `Manager` or `Factory` that only forwards construction may be less clear than direct value construction. Before deleting it, check dependency injection, allocation, platform selection, registration, transaction, and ABI boundaries. Delete abstractions only when they own no durable policy.

## Verification

Use repository-local commands and the supported matrix. A proportionate sequence is:

1. Formatter in check or scoped write mode.
2. Compile affected targets with the repository warning policy in debug and relevant release/configuration modes.
3. Run targeted unit and integration tests, then broader tests for shared headers or public libraries.
4. Run `clang-tidy` or the configured static analyzer on changed code without introducing broad suppressions.
5. Run AddressSanitizer and UndefinedBehaviorSanitizer for lifetime/memory/UB-sensitive work.
6. Run ThreadSanitizer separately for changed concurrency where the platform supports it.
7. Build supported compilers, standard libraries, platforms, and feature combinations when public or portability-sensitive code changed.
8. Run ABI/export checks, FFI tests, benchmarks, or allocation probes when those contracts are in scope.
9. Review optimized-build behavior and the final diff against the preservation ledger.

Sanitizer combinations and platform support vary; follow project configuration rather than inventing unsupported flag sets. Warnings are valuable but are not a language specification, and `-Werror` policy should not be imposed on external or previously unclean code as incidental cleanup.

## C++ completion checklist

- The language/library version and compiler/platform matrix remain supported.
- Ownership, nullability, borrowing, lifetime, copying, and moving are explicit and correct.
- Resource release and partial-failure behavior are protected by RAII.
- Special members express the intended value, move-only, or immovable semantics.
- Public source, ABI, layout, FFI, serialization, and exception contracts did not drift accidentally.
- Initialization, overload resolution, conversions, and evaluation order remain deliberate.
- Errors retain meaning and the intended exception-safety guarantee.
- Templates and abstractions encode real variation without unnecessary compile-time or API cost.
- Iterators, references, views, and callbacks cannot outlive or be invalidated by their owners unexpectedly.
- Concurrency has explicit synchronization, ordering, cancellation, and shutdown ownership.
- Casts and low-level operations have narrow, documented preconditions; no new undefined behavior was introduced.
- Performance changes are justified by semantics or evidence, not folklore.
- Headers are self-contained, linkage is correct, generated files are untouched, and targeted checks pass in relevant configurations.

## Primary guidance

These sources provide engineering guidance and semantic/tooling references; they do not replace the project's requirements or the normative ISO C++ standard.

- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
- [cppreference: RAII](https://en.cppreference.com/w/cpp/language/raii)
- [cppreference: Object lifetime](https://en.cppreference.com/w/cpp/language/lifetime)
- [cppreference: Copy and move semantics](https://en.cppreference.com/w/cpp/language/rule_of_three)
- [cppreference: Memory model](https://en.cppreference.com/w/cpp/language/memory_model)
- [Clang AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html)
- [Clang UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)
- [Clang ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html)
- [clang-tidy](https://clang.llvm.org/extra/clang-tidy/)
- [CMake build-system manual](https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html)
