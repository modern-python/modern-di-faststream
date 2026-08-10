# Dependency injection

The capability this package exists for: wiring a `modern-di` `Container` into a
FastStream app so subscriber parameters resolve from it, scoped per message.
Everything lives in `modern_di_faststream/main.py`; the public surface is
`setup_di`, `FromDI`, `fetch_di_container`, and `faststream_message_provider`.

## Setup

`setup_di(app, container)` is the single entry point. It:

1. Registers `faststream_message_provider` on the container so the current
   `faststream.StreamMessage` is resolvable inside DI (a `ContextProvider` bound
   to `Scope.REQUEST`).
2. Stores the container in the app's `ContextRepo` under `_ROOT_CONTAINER_KEY`.
3. Pairs `container.open` (on startup) with `container.close_async` (after
   shutdown) so the root container's lifecycle tracks the app's.
4. Adds the DI middleware to the broker.

It raises `RuntimeError("Broker must be defined to setup DI")` if `app.broker`
is unset — DI has nothing to attach to without a broker.

## The container handoff seam

Containers are handed between the package's parts through FastStream's
`ContextRepo`, under two **named** keys (constants in `main.py`, never bare
literals — see [decision][d-factory] siblings):

| key | scope | writer | reader |
| --- | --- | --- | --- |
| `_ROOT_CONTAINER_KEY` (`"di_container"`) | app | `setup_di` | `fetch_di_container` |
| `_REQUEST_CONTAINER_KEY` (`"request_container"`) | per message | `_DiMiddleware.consume_scope` | `Dependency.__call__` |

Naming the keys keeps each writer and reader in provable agreement; a mismatch
is a `NameError` at import, not a silent runtime miss.

## Per-message scope

`_DiMiddleware` (constructed by `_DIMiddlewareFactory`, which binds the
container ahead of FastStream's deferred middleware construction — see
[the decision to keep the two-class split][d-factory]) runs `consume_scope` on
every message.

The factory declares FastStream's construction contract literally —
`__call__(msg, /, *, context: ContextRepo) -> _DiMiddleware`, mirrored on
`_DiMiddleware.__init__` — so `broker.add_middleware(_DIMiddlewareFactory(...))`
is checked against the `BrokerMiddleware` protocol at type-check time. That
call site is the package's guard against FastStream changing the contract
underneath it: a mismatch is a `ty` error, not a first-message runtime failure.

On each message the middleware:

1. `modern_di.integrations.bind(faststream_message_provider, msg)` derives the
   child's scope and context from the message — `bind(provider, connection)`
   returns `ConnectionMatch(scope=provider.scope,
   context={provider.context_type: connection})`, so this always produces
   `scope=REQUEST, context={StreamMessage: msg}`, the same values the code
   used to hand-write. FastStream is broker-agnostic through this one message
   type, so there is only ever one provider to derive from —
   `classify_connection` (which dispatches across several providers) has
   nothing to dispatch across here.
2. `self.di_container.build_child_container(scope=match.scope,
   context=match.context)` builds the child, opened via `Container`'s own
   `async with` — entering an already-open container is a no-op; exiting
   closes it, including on the exception path. This replaces the old manual
   `try`/`finally: await request_container.close_async()`.
3. Inside that block, a plain sync `with
   self.context.scope(_REQUEST_CONTAINER_KEY, request_container):` still
   scopes the child into `ContextRepo` for the duration of the call —
   `ContextRepo.scope` is not an async context manager, so the two blocks
   nest rather than combine into one `async with A, B:` statement.

## Resolution

`FromDI(dependency, *, use_cache=True, cast=False)` returns a FastStream
`Depends` wrapping a `Dependency` instance holding a
`modern_di.integrations.Marker(dependency)`. At resolution time `Dependency`
reads the request container out of `ContextRepo` and calls
`self.marker.resolve(request_container)`, which is
`container.resolve_dependency(self.dependency)` under the hood — dispatching
to:

- an `AbstractProvider` → `resolve_provider(...)`,
- a bare `type` → `resolve(dependency_type=...)`.

`Dependency` is the deep part of this seam — the container lookup and the
`Marker` delegation sit behind a single `__call__`. `FromDI` is just its
constructor.

## Lifecycle note

FastStream's lifecycle is callback-based, so the root container can't be wrapped
in `async with`. `setup_di` reopens it on startup (reopening an already-open
container is a no-op) to pair with the shutdown close, so a broker restart
rebuilds request children instead of raising `ContainerClosedError`.

[d-factory]: ../planning/decisions/2026-06-25-keep-dimiddlewarefactory.md
