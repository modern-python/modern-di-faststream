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

## Revisit outcome — 2026-08-10: reopened, decision re-affirmed

The second trigger fired. [Typing the factory to FastStream's real
`(msg, /, *, context: ContextRepo)` contract][c-typed] made the forwarding
type-clean and dropped both `# ty: ignore[invalid-argument-type]` comments, so
`functools.partial(_DiMiddleware, container)` was built and measured against the
named factory. Both pass `ty`, ruff, and the suite; `partial` is ~10 LOC
shorter.

**Keep the split anyway — on a ground this decision did not originally have.**
The above predicted `partial` "almost certainly keeps the same `# ty: ignore`";
that prediction is now false, so the original argument no longer decides. What
decides instead is *type-checkability at the registration seam*:

`functools.partial` types as `(*args: Any, **kwargs: Any)`, which is assignable
to **any** protocol. Under `partial`, breaking the construction contract — e.g.
renaming `_DiMiddleware.__init__`'s `context` keyword — leaves `ty` reporting
`All checks passed!`, and the mismatch surfaces at runtime on the first message.
With the explicit factory, the same break is a compile-time error at
`add_middleware`: *"`_DIMiddlewareFactory` is not assignable to protocol
`BrokerMiddleware[Any, Any]` ... parameter `context` is missing"*.

That reframes the deletion test. The factory is not a pass-through whose
complexity merely *moves* — it is the site where this package's adaptation to
FastStream's contract is **asserted and checked**. Deleting it deletes the
check. For a package whose whole job is that adaptation, and which just spent
two release cycles with the mismatch masked by `ty: ignore`s, the ~10 LOC buy a
real guard against silent upstream drift.

**New revisit trigger:** `functools.partial` (or the call site) gains precise
signature typing such that a contract break is caught at `add_middleware`, **or**
FastStream starts accepting a pre-bound middleware instance. Either removes the
factory's remaining justification.

[c-typed]: ../changes/2026-08-10.01-middleware-contract-typed.md
