---
status: accepted
summary: Kept the `_DIMiddlewareFactory`/`_DiMiddleware` two-class split — it adapts FastStream's middleware-construction contract, so collapsing it moves complexity rather than concentrating it.
supersedes: null
superseded_by: null
---

# Keep the `_DIMiddlewareFactory` two-class split

**Decision:** Keep `_DIMiddlewareFactory` as a distinct class that binds the
container and constructs `_DiMiddleware`, rather than collapsing the two into a
single class.

## Context

An architecture review flagged `_DIMiddlewareFactory`
(`modern_di_faststream/main.py`) as a possible shallow module: a one-method
class whose `__call__` only binds `di_container` and forwards `*args/**kwargs`
through a `ParamSpec` to `_DiMiddleware`, carrying a
`# ty: ignore[invalid-argument-type]`. On the surface it reads as a pass-through
worth folding away — e.g. with `functools.partial`, a closure, or a classmethod
constructor.

## Decision & rationale

Leave it as two classes.

The deletion test is the deciding lens: delete the factory and the
container-binding complexity **moves** to whatever replaces it — it does not
**concentrate**. There is no net simplification on offer.

The factory is the **adapter** to FastStream's middleware-construction contract.
`broker.add_middleware(...)` expects a callable that FastStream later invokes as
`(msg, /, *, context: ContextRepo)` and which must return a `BaseMiddleware`
instance. The container has to be bound *ahead* of that deferred call, so some
carrier for `di_container` is unavoidable. The named class is the most legible
carrier:

- `functools.partial` / a closure trades the named, `__slots__`-ed class for a
  less greppable binding and almost certainly keeps the same `# ty: ignore` on
  the `ParamSpec` forwarding.
- A classmethod constructor still needs an instance to hold `di_container`,
  reintroducing the same state the factory already names.

Leverage is low either way; the explicit factory is the clearest form. The
two-class split earns its keep as an adapter, not a wrapper.

## Revisit trigger

FastStream changes its middleware-registration contract so `add_middleware`
accepts a pre-bound middleware instance (removing the need for a deferred
factory), **or** the `ParamSpec` forwarding becomes type-clean so the
`# ty: ignore` can be dropped. At that point collapsing into a single class or a
`partial` becomes a genuine simplification and this decision should be reopened.
