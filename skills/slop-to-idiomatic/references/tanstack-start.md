# Idiomatic TanStack Start

Use this reference with the TypeScript and React references. TanStack Start idioms center on explicit execution boundaries, typed routing, route-owned data, server-function security, serialization, and SSR-safe behavior.

TanStack Start evolves faster than TypeScript or core React. Inspect installed `@tanstack/*` versions and the matching documentation before changing APIs. Do not copy an example from another major, adapter, build tool, or experimental feature into the project.

## Map the application before editing

Identify:

- Start, Router, Query, React, Vite/Rsbuild, and deployment adapter/runtime versions.
- File-based or code-based routing, generated route-tree location, and route naming conventions.
- SSR, streaming, pre-rendering, Server Components, and hydration configuration.
- Data ownership: route loaders, server functions, server routes, TanStack Query, or another client cache.
- Authentication/session middleware and where authorization is enforced.
- Runtime environment model: Node, Bun, edge/worker, serverless, or a custom fetch handler.
- Existing `.server.*`, `.functions.*`, shared schema, middleware, and route organization.

Do not edit generated route-tree files. Do not change route filenames casually: they determine route IDs, nesting, URLs, and generated types.

## Know where code executes

Code is isomorphic by default unless constrained. A route loader can run on the server for the initial SSR request and in the browser during client navigation.

Classify every changed operation:

| Operation | Appropriate boundary |
|---|---|
| Pure formatting/domain calculation safe in both runtimes | Shared isomorphic module |
| App-internal database, secret, filesystem, or privileged operation | Server function calling server-only code |
| Public/cross-origin webhook or raw HTTP endpoint | Server route |
| Environment-specific utility without an RPC call | Server-only/client-only/isomorphic function helper |
| Navigation data | Route loader, often calling a server function |
| Client cache/mutation lifecycle | Established TanStack Query integration or route invalidation pattern |

Never import database clients, private environment modules, filesystem code, or secret-bearing configuration into an isomorphic route/component module. A TypeScript import being type-safe does not make it bundle-safe.

Use environment-control helpers or `.server.*` boundaries supported by the installed version. Keep server-only imports inside server-constrained modules/callbacks according to the framework's compilation rules.

## Let routes own navigation concerns

Prefer file-based routing when the repository already uses it; it is the framework's conventional path. A route module should keep route lifecycle concerns discoverable:

- `validateSearch` parses untrusted URL state.
- `loaderDeps` declares the validated values that make loader output distinct.
- `beforeLoad` supplies route context, redirects early for UX, or prevents pointless work.
- `loader` loads navigation data.
- `pendingComponent`, `errorComponent`, and `notFoundComponent` describe route outcomes.
- The route component reads typed params/search/loader data through its route API.

Avoid a giant root route that performs unrelated feature loading and permission logic. Avoid hiding route loaders behind generic “controller” wrappers that erase typed params, dependencies, abort signals, or framework errors.

### Treat URL input as untrusted

Search params originate as user-controlled text even when the router parses them into JSON-like values. Validate and default them at the route boundary.

```tsx
const searchSchema = z.object({
  page: z.coerce.number().int().positive().catch(1),
  query: z.string().catch(''),
})

export const Route = createFileRoute('/products')({
  validateSearch: searchSchema,
  loaderDeps: ({ search: { page, query } }) => ({ page, query }),
  loader: ({ deps }) => getProducts({ data: deps }),
})
```

Use the project's validator integration and version-correct API. Preserve existing canonicalization, defaults, replace/push history behavior, and serialization when refactoring search params.

Use path params for resource identity in the route hierarchy and search params for shareable/filter/sort/pagination state. Keep ephemeral widget state local to React.

### Declare loader dependencies

If loader output depends on search or other route inputs, include their validated form in `loaderDeps`. This makes cache/reload behavior explicit and typed. Do not close over undeclared mutable values or read raw URL state inside generic helpers.

Preserve `staleTime`, `gcTime`, preloading, `shouldReload`, and invalidation behavior. Moving data between a loader and Query can change request deduplication, cache ownership, pending UI, and SSR dehydration.

## Use server functions as app-internal RPC boundaries

A server function is an endpoint, even when it looks like a local function call. It should be thin and explicit:

1. Choose the HTTP method that matches read versus mutation semantics.
2. Validate the single input at runtime.
3. Authenticate and authorize at this endpoint.
4. Call cohesive server-only domain/persistence code.
5. Return only intentional, serializable data.
6. Translate expected errors to the framework/domain contract without leaking secrets.

```ts
// orders.functions.ts — safe RPC wrapper to import from app code
export const getOrder = createServerFn({ method: 'GET' })
  .validator(orderIdSchema)
  .handler(async ({ data: orderId }) => {
    const session = await requireSession()
    return findAuthorizedOrder(session.userId, orderId)
  })
```

```ts
// orders.server.ts — never import from client/isomorphic code
export async function findAuthorizedOrder(userId: string, orderId: string) {
  return db.query.orders.findFirst(/* authorization-constrained query */)
}
```

Use static imports for server functions as documented by Start; the build replaces the implementation with a client RPC stub. Avoid dynamic imports of server functions unless the installed version explicitly supports them.

### Validate across the network boundary

TypeScript checks do not validate requests. Use the existing schema library/validator for every nontrivial server-function input. Keep shared schemas client-safe: schemas must not import server modules or secrets.

Inputs and outputs cross a serialization boundary. Do not return database handles, class instances with required prototypes, closures, non-supported platform objects, or oversized internal records. Map persistence models to intentional response shapes when the boundary differs.

Preserve exact dates, undefined/omitted fields, errors, headers, status, redirects, and not-found behavior supported by the installed serializer.

### Authorize the data boundary

`beforeLoad` is useful route UX, not the security boundary. A caller can reach a server function or server route independently of the screen that normally invokes it.

- Authenticate and authorize every endpoint that reads or mutates private data.
- Prefer reusable server middleware for consistent session/context behavior when the project has multiple endpoints.
- Keep resource-level authorization in the operation/query, not only in a global “logged in” check.
- Validate CSRF/same-origin protection according to the Start version and custom `src/start.ts` configuration.
- Never trust user IDs, tenant IDs, prices, roles, or ownership claims merely because they came from a typed client.

Do not weaken endpoint checks because a route already redirects unauthorized users.

## Use server routes for HTTP, not internal calls

Choose a server route when consumers need a real HTTP contract: webhooks, third-party callbacks, public APIs, cross-origin clients, raw/binary responses, custom content negotiation, or protocol-specific status/headers.

Choose a server function for calls from the Start application that benefit from typed RPC and framework serialization.

Do not wrap every server function in a server route or call the application's own internal HTTP route from the server unless the HTTP boundary is intentional. Direct server-domain calls avoid redundant serialization and make transactions/context easier to own.

For server routes, preserve:

- HTTP method and idempotency.
- Status codes, headers, body/content type, and streaming.
- Authentication/signature verification and raw-body requirements.
- CORS, caching, rate limiting, and retry semantics.
- External compatibility independent of generated TypeScript types.

## Keep middleware scoped and composable

Use request middleware for concerns that truly apply to broad request classes. Use server-function middleware for behavior specific to RPC calls. Prefer narrow middleware for authentication context, tracing, headers, or policy that multiple handlers share.

Avoid middleware that:

- Hides endpoint-specific authorization.
- Mutates unrelated global/module state.
- Swallows redirects, not-found responses, or typed errors.
- Performs expensive work on routes that do not need it.
- Makes execution order essential but undocumented.
- Returns broad untyped context bags.

Keep context values minimal, typed, and request-scoped. Never store per-request user/session/database transaction state in module globals; SSR processes multiple users in one runtime.

## Coordinate route loaders and TanStack Query deliberately

Both the router and Query can cache data. Give each resource one clear ownership strategy:

- Router-only for navigation-scoped data with route stale/reload semantics.
- Query for reusable client cache, background refresh, mutations, and invalidation.
- Router loader + Query integration when the loader ensures/prefetches the same query and the component consumes it from Query.

Do not independently fetch the same resource in a loader, a mount Effect, and a query hook. Align query keys and loader dependencies so SSR, navigation, and invalidation address the same identity.

When refactoring, preserve:

- Cache/query key shape and tenant/user scoping.
- Stale and garbage-collection times.
- Retry behavior and error ownership.
- Prefetch versus blocking navigation.
- Dehydration/hydration and duplicate-request prevention.
- Optimistic update rollback and mutation invalidation.

Route loaders should call server functions for privileged data rather than importing server-only repositories directly, because loaders also run in the browser during client navigation.

## Use framework-native navigation outcomes

Use typed navigation and route APIs rather than string concatenation. Use the framework's redirect and not-found primitives so router lifecycles, SSR status, and error components behave consistently.

- Throw/return redirects exactly as required by the installed API and call site.
- Distinguish not-found resources from authorization and unexpected failures.
- Keep route error components from exposing internal server messages or stack traces.
- Preserve status codes during SSR and server-route handling.
- Do not catch a framework redirect/not-found value and convert it into a generic 500.

Generated code often catches `unknown` around an entire loader and returns an empty array. Remove this fallback only after determining whether empty data is an intentional UX contract. Prefer route errors for unexpected failures and explicit empty states for successful zero-result responses.

## Keep mutations close to their lifecycle

For forms and actions:

- Validate on the server even if the client validates.
- Preserve native form/progressive-enhancement behavior when present.
- Prevent or make duplicate submissions idempotent according to domain requirements.
- Represent pending and field/form errors without duplicating several unsynchronized flags.
- Redirect or invalidate the exact affected route/query after success.
- Keep optimistic UI paired with rollback and authoritative server validation.
- Do not return sensitive persistence errors to the browser.

Event handlers may invoke server functions through the version-correct client adapter/hook. Avoid using an Effect to observe “should submit” state.

## Preserve SSR and hydration correctness

Server rendering cannot use browser-only globals or per-browser storage directly.

- Keep `window`, `document`, `localStorage`, DOM measurement, and browser subscriptions behind a client-only boundary or post-render synchronization.
- Make the first client render compatible with server HTML; do not use random values, current time, locale, or module-level mutable counters without a deterministic strategy.
- Do not share user-specific data through module-level caches.
- Ensure serialization/dehydration includes the data needed for hydration without leaking secrets.
- Preserve streaming and Suspense boundary placement; moving awaits can change time-to-first-byte and reveal content in a different order.
- Use environment helpers for code that intentionally differs by runtime rather than ad hoc `typeof window` branches scattered across domain code.

Environment variables are a security boundary. Publicly prefixed variables are client-visible. Read secrets only from server-constrained code. On request-injected edge runtimes, follow the adapter's request-context/env binding pattern rather than assuming module-scope `process.env` is populated.

## Cache only with identity and privacy understood

- Public, identical data may use shared caching with deliberate keys and invalidation.
- Personalized/authenticated data should default to private or no-store behavior unless cache partitioning by identity is proven.
- Preserve `Vary`, cookies, authorization headers, and deployment CDN behavior.
- Do not make a server function static/cacheable solely for speed if it reads request context, time, feature flags, or private data.
- Ensure cache keys include every input and identity dimension that affects output.

Caching changes behavior. Treat it as an explicit performance feature with tests, not cleanup.

## Organize by boundary, then feature

Use the repository's convention. For a larger feature, a clear split is often:

```text
orders/
  orders.schemas.ts      # client-safe validation/types
  orders.functions.ts    # createServerFn RPC wrappers
  orders.server.ts       # database/secrets/server-only domain work
  orders.queries.ts      # client-safe query options/keys, if used
  OrdersPage.tsx         # UI
```

The suffix is less important than enforced import direction. Avoid central `serverFunctions.ts`, `utils.ts`, or `api.ts` files that mix unrelated domains and invite server/client leakage.

Keep route modules readable. Extract server/domain work, query option factories, or substantial UI—not tiny wrappers that make following one route require six files.

## Common refactors

### Move privileged loader code behind a server function

```tsx
// Avoid: loaders are isomorphic.
export const Route = createFileRoute('/admin/users')({
  loader: () => db.query.users.findMany(),
})

// Prefer
const listUsers = createServerFn({ method: 'GET' })
  .handler(async () => {
    const admin = await requireAdmin()
    return listUsersForAdmin(admin)
  })

export const Route = createFileRoute('/admin/users')({
  loader: () => listUsers(),
})
```

Keep the server function in the project's server-function module rather than in the route if that is the established boundary.

### Replace component Effect fetching with route data

```tsx
export const Route = createFileRoute('/orders/$orderId')({
  loader: ({ params }) => getOrder({ data: params.orderId }),
  component: OrderPage,
})

function OrderPage() {
  const order = Route.useLoaderData()
  return <OrderDetails order={order} />
}
```

Before migrating, preserve loading UI, cancellation, refetching, caching, and client-only needs. Use Query integration when the data must stay live beyond navigation.

### Separate route guard UX from authorization

Keep an early `beforeLoad` redirect for a better navigation experience, and retain an independent server-side authorization check inside every private endpoint. Share the session/authorization primitive, not an assumption that the route always ran first.

## Verification

Use project-local scripts and the supported runtime/adapter. Cover:

1. Formatting, TypeScript checking, and linting.
2. Route-tree generation/build; confirm generated output is clean and not hand-edited.
3. Targeted route component/loader/server-function tests.
4. Direct unauthorized calls to each changed private endpoint.
5. Input-validation, redirect, not-found, and error cases.
6. Initial SSR request and client-side navigation to the same route.
7. Hydration without mismatch warnings.
8. Mutation success, validation failure, duplicate submit, and invalidation/redirect behavior.
9. Production build for client/server leakage and adapter compatibility.
10. Cache/privacy behavior when caching changed or personalized data is involved.

If execution infrastructure is unavailable, at minimum type-check, build, inspect client output/import graphs for server-only leakage, and state which runtime paths remain unverified.

## TanStack Start completion checklist

- Every changed operation has an intentional isomorphic, client-only, or server-only home.
- Route files and generated route types remain consistent.
- Search/params are validated and loader dependencies capture output identity.
- Private server functions/routes validate and authorize at the endpoint.
- Server-function inputs/outputs are serializable and expose only deliberate data.
- Router and Query have one coherent cache/data-ownership plan.
- Redirect, not-found, pending, error, and mutation outcomes use framework primitives.
- SSR, hydration, streaming, and browser-only APIs remain safe.
- Secrets and per-request state cannot reach client bundles or module-global shared state.
- Deployment adapter, version, caching, and external HTTP contracts remain compatible.

## Primary guidance

- [TanStack Start overview](https://tanstack.com/start/latest/docs/framework/react/overview)
- [TanStack Start execution model](https://tanstack.com/start/latest/docs/framework/react/guide/execution-model)
- [TanStack Start server functions](https://tanstack.com/start/latest/docs/framework/react/guide/server-functions)
- [TanStack Start server routes](https://tanstack.com/start/latest/docs/framework/react/guide/server-routes)
- [TanStack Start authentication](https://tanstack.com/start/latest/docs/framework/react/guide/authentication)
- [TanStack Router file-based routing](https://tanstack.com/router/latest/docs/routing/file-based-routing)
- [TanStack Router data loading](https://tanstack.com/router/latest/docs/guide/data-loading)
- [TanStack Router search params](https://tanstack.com/router/latest/docs/framework/react/guide/search-params)
