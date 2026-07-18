# Idiomatic React

Use this reference with the language reference for the project's source language. React idioms are primarily about render purity, state ownership, lifecycle boundaries, and composition—not hook-shaped syntax.

## Establish the React contract

Before editing, identify:

- React version and whether the React Compiler is enabled.
- Rendering model: client-only, SSR, streaming, Server Components, or a framework such as TanStack Start.
- The router/data library that owns loading, mutations, caching, and errors.
- Strict Mode behavior and existing component-test conventions.
- Observable UI contracts: accessible name/role, focus, keyboard behavior, form semantics, animation, URL state, hydration output.

Do not apply client-component patterns to server-only code or introduce version-specific APIs unsupported by the repository.

## Render is a pure calculation

A component or hook must be idempotent for the same props, state, and context. During render:

- Do not mutate props, state, context, module state, hook arguments, or previously created JSX values.
- Do not perform I/O, subscriptions, navigation, analytics, timers, DOM writes, or state updates in other components.
- Do not depend on render order or the component being called exactly once.
- Do not call components as ordinary functions; render them through JSX.
- Keep hooks at the top level of React components or custom hooks.

Local mutation of a value created during the current render can be fine when it cannot escape and remains deterministic. Purity is about observable effects, not banning every `push`.

## Make state minimal and owned

State is the smallest mutable source of truth needed to describe interaction over time.

### Derive instead of synchronize

```tsx
// Avoid: redundant state, stale render, extra Effect.
const [fullName, setFullName] = useState('')
useEffect(() => setFullName(`${firstName} ${lastName}`), [firstName, lastName])

// Prefer
const fullName = `${firstName} ${lastName}`
```

Do not store values that are cheap, deterministic functions of current props/state. Memoize an expensive pure derivation only when measurement or a downstream identity contract justifies it.

### Design state to exclude contradictions

- Group values updated atomically when separate setters allow inconsistent intermediate states.
- Use a discriminated union or reducer for meaningful workflow states and transitions.
- Store stable identifiers rather than duplicate copies of objects that may update.
- Keep state flat enough to update clearly; normalize collections when multiple places reference the same entity.
- Do not mirror props into state unless the component intentionally captures an initial value or owns a draft. Name that intent (`initialName`, `draftName`).

Use `useReducer` when named transitions and centralized invariants make behavior clearer. Do not replace several independent booleans with a reducer merely to appear architectural.

### Put state at the lowest common owner

- Keep state local when no sibling needs it.
- Lift it to the nearest shared owner when several children must coordinate.
- Use context for ambient, cross-cutting data or a stable subsystem boundary—not to avoid passing two props.
- Split frequently changing context values or use an external store when broad rerenders are material.
- Use the framework/router URL model for shareable navigation state rather than duplicating it in component state.

Component identity is position plus type and key. Use a deliberate `key` to reset a subtree when identity changes. Never generate keys during render or use array indexes for reorderable/stateful items.

## Effects synchronize external systems

An Effect is appropriate when a rendered component must synchronize with something React does not own: a DOM/imperative widget, subscription, timer, network connection, browser API, or external store.

Before adding or retaining an Effect, ask:

1. Can this value be calculated during render?
2. Did a specific user action cause the work? Put it in that event handler.
3. Does the router or data library already own this fetch/mutation/cache lifecycle?
4. Can changing a `key`, lifting state, or subscribing through a purpose-built hook express it directly?
5. What external resource is being synchronized, and what cleanup reverses setup?

```tsx
// Avoid: the Effect loses which user action caused the purchase.
useEffect(() => {
  if (shouldBuy) void purchase(productId)
}, [shouldBuy, productId])

// Prefer
async function handlePurchase() {
  await purchase(productId)
}
```

For every retained Effect:

- Include every reactive value it reads; restructure code instead of suppressing dependency checks.
- Make setup/cleanup symmetrical and safe under development remounts.
- Handle cancellation or stale async completion.
- Avoid effects that immediately set derived state, chain into other effects, or recreate a state machine indirectly.
- Keep event-specific logic in events even if an Effect can observe the resulting state.

Use `useSyncExternalStore` for external stores that must integrate consistently with concurrent rendering and SSR. Do not hand-roll subscription effects when an official adapter exists.

## Use framework data primitives

When a framework or established data library is present, prefer its loaders, actions/mutations, cache, pending state, cancellation, error boundary, and invalidation model over `fetch` in mount Effects.

This usually provides:

- Data before or during navigation rather than after a blank render.
- Request deduplication, caching, invalidation, retries, and cancellation with one owner.
- SSR/streaming integration and fewer hydration waterfalls.
- Route-level pending, not-found, and error behavior.

Do not migrate a working data layer as incidental cleanup. First understand cache keys, stale times, optimistic updates, authorization, and error semantics.

## Prefer cohesive components and behavior-bearing hooks

A component should represent a meaningful UI responsibility. Extract when it:

- Has a name that clarifies the parent.
- Owns a cohesive interaction or rendering concern.
- Is reused with the same semantics.
- Is large because it contains an independently reasoned subtree—not merely because it crossed a line count.

Avoid fragmenting markup into one-use components that only forward props and obscure layout. Conversely, do not keep unrelated state, effects, and markup in a single “page” component.

A custom hook should package reusable stateful behavior or an external-system adapter. It should expose an intention-revealing interface and keep React lifecycle rules internal.

Avoid hooks that:

- Merely rename one built-in hook.
- Return an oversized bag of unrelated state and setters.
- Hide imperative side effects behind a getter-like name.
- Accept configuration objects recreated every render without a stability strategy.
- Make ownership less clear than keeping the code in the component.

Keep presentational and domain/data concerns separable where it improves testing and reuse, but do not force “container/presentational” layers into every feature.

## Compose APIs that make valid use obvious

- Prefer explicit props with domain names over generic `data`, `config`, and boolean mode flags.
- Use children/slots for visual composition when the parent should not know child internals.
- Use controlled components when the parent owns the value; uncontrolled components when local DOM/component ownership is intentional. Do not switch modes during a component lifetime.
- Avoid copying every prop to a wrapper. Forward only the surface the wrapper truly supports, or use an established polymorphic/component primitive carefully.
- Preserve ref semantics when introducing wrappers; in modern React versions follow the project's supported ref API rather than assuming one version.
- Use context providers as subsystem APIs with narrow values, clear defaults, and failure behavior for missing providers.

Boolean props often hide multiple visual modes (`<Modal compact dark centered />`). Prefer named variants or composition when combinations have distinct semantics, but keep a simple boolean for a genuine on/off capability.

## Keep events and forms semantic

- Name handlers for the domain event (`handleOrderSubmit`), not only the DOM event (`handleClick`), when intent matters.
- Pass a function to an event prop; do not invoke it during render.
- Preserve event propagation/default behavior deliberately when moving handlers.
- Prefer semantic HTML and native form behavior before recreating it with divs and keyboard handlers.
- Keep labels, roles, accessible names, focus order, focus restoration, and validation announcements intact.
- Avoid storing synthetic event objects for later work; extract the needed values.
- For forms, preserve disabled/pending behavior, duplicate-submit prevention, native submission/progressive enhancement, and server validation.

Accessibility is observable behavior, not polish. A visually identical refactor that removes keyboard or screen-reader behavior is a regression.

## Use memoization for a reason

`memo`, `useMemo`, and `useCallback` are performance and identity tools, not default markers of quality.

Keep or add them when at least one is true:

- Profiling identifies meaningful repeated work.
- A memoized child can actually skip expensive renders when an input is stable.
- A value's stable identity is required by an Effect, subscription, context, or third-party API.
- The calculation is sufficiently expensive and dependencies are correct.

Remove cargo-cult memoization when it adds dependency complexity without preventing work. Check React Compiler configuration before manual memoization cleanup; preserve explicit identity contracts even when the compiler optimizes rendering.

Do not move objects/functions to module scope if they close over per-request data, are mutated, or make SSR requests share state.

## Refs are escape hatches

Use refs for values that must persist without driving render, or for imperative integration. Do not read/write `ref.current` during render except safe initialization patterns supported by React.

- If changing the value should update UI, use state.
- Expose the smallest imperative handle a parent needs.
- Keep DOM manipulation compatible with React's ownership of that DOM.
- Preserve focus and measurement timing; choose layout effects only when pre-paint measurement is required and supported by the rendering environment.

## Handle async UI as state, not scattered flags

- Represent pending, success, empty, not-found, and error states explicitly.
- Keep mutation state separate from unrelated route/query loading when their lifecycles differ.
- Prevent stale response commits or delegate that ownership to the data library.
- Put recoverable rendering failures behind an appropriate error boundary.
- Use Suspense only with a Suspense-aware data source/framework; wrapping arbitrary Effect fetching does not make it Suspense-compatible.
- Keep SSR output deterministic. Browser-only values need a deliberate client boundary or hydration-safe subscription pattern.

## Test behavior at the user boundary

Refactor tests should prefer what users and integrators observe:

- Roles, accessible names, visible state, navigation, submitted data, and focus.
- State transitions caused by user actions.
- Setup/cleanup of external subscriptions.
- Route/data integration where the framework owns behavior.

Avoid asserting hook call order, internal state shape, component instance structure, or implementation-only class names unless they are contracts. Use Strict Mode in tests where the project does; it exposes unsafe render effects and incomplete cleanup.

## Common refactors

### Collapse an Effect chain into one event transition

```tsx
// Before: one click causes several renders and synchronization paths.
const [draft, setDraft] = useState<Order | null>(null)
const [shouldSave, setShouldSave] = useState(false)

useEffect(() => {
  if (shouldSave && draft) {
    void saveOrder(draft)
    setShouldSave(false)
  }
}, [draft, shouldSave])

// After
async function handleSave(draft: Order) {
  await saveOrder(draft)
}
```

Preserve double-submit, error, pending, and cancellation behavior when making this change.

### Store identity, derive the object

```tsx
const [selectedId, setSelectedId] = useState<string | null>(null)
const selected = items.find((item) => item.id === selectedId) ?? null
```

This avoids a stale duplicated object when `items` refresh. Confirm what should happen if the selected item disappears.

### Replace a hook-shaped pass-through

```tsx
// Before
function useCurrentTheme() {
  return useContext(ThemeContext)
}
```

Keep this wrapper if it enforces a provider, narrows the public API, stabilizes migration, or gives a domain name used throughout the app. Delete it only when it truly adds no contract.

## React completion checklist

- Rendering is pure and safe to repeat, pause, or abandon.
- State has one clear owner and does not duplicate derivable values.
- Impossible workflow states are reduced rather than synchronized by effects.
- Every Effect names a real external system, has complete dependencies, and cleans up.
- Events own event-caused work; the router/data layer owns its lifecycle.
- Component and hook boundaries clarify responsibilities instead of adding forwarding layers.
- Keys, refs, memoization, context, and callbacks have explicit identity reasons.
- SSR/hydration and client/server boundaries remain correct.
- Semantic HTML, accessibility, focus, and form behavior are preserved.
- Tests assert user-visible behavior and critical integrations.

## Primary guidance

- [Rules of React](https://react.dev/reference/rules)
- [Keeping Components Pure](https://react.dev/learn/keeping-components-pure)
- [Choosing the State Structure](https://react.dev/learn/choosing-the-state-structure)
- [You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect)
