# Keep the `_DIMiddlewareFactory` two-class split

**Decision:** Keep `_DIMiddlewareFactory` as a distinct class that binds the container and
constructs `_DiMiddleware`, rather than collapsing the two into one class, a closure, or a
`functools.partial`.

## Why it keeps coming up

`_DIMiddlewareFactory` reads as a shallow module: a one-method class whose `__call__` binds
`di_container` and forwards to `_DiMiddleware`. On the surface it is a pass-through worth folding
away. The deletion test appears to agree — delete it and the `setattr`-like binding simply inlines.

The original decision (2026-06-25) kept it on a *complexity moves, not concentrates* argument: the
container must be bound ahead of FastStream's deferred middleware construction, so some carrier is
unavoidable, and a named `__slots__`-ed class is the most legible carrier. That argument leaned on
a prediction — that `functools.partial` would still need the same
`# ty: ignore[invalid-argument-type]` on its `ParamSpec` forwarding.

## Why it survives the collapse being possible

That prediction is now false. Typing the factory to FastStream's real
`__call__(msg, /, *, context: ContextRepo) -> _DiMiddleware` contract (#39) made the forwarding
type-clean and dropped both `ty` suppressions, so `functools.partial(_DiMiddleware, container)` was
built and measured against the named factory. Both pass `ty`, `ruff`, and the suite; `partial` is
about ten lines shorter. The original argument no longer decides.

What decides instead is **type-checkability at the registration seam**. `functools.partial` types
as `(*args: Any, **kwargs: Any)`, which is assignable to *any* protocol. Under `partial`, renaming
`_DiMiddleware.__init__`'s `context` keyword leaves `ty` reporting `All checks passed!` and the
mismatch surfaces at runtime on the first message. With the explicit factory, the same break is a
type error at `broker.add_middleware(...)`: `_DIMiddlewareFactory` is not assignable to
`BrokerMiddleware[Any, Any]`, parameter `context` is missing.

So the factory is not a pass-through whose complexity merely moves. It is the site where this
package's adaptation to FastStream's construction contract is asserted and checked; deleting it
deletes the check. For a package whose entire job is that adaptation, and which spent two release
cycles with the mismatch masked by `ty` suppressions, ten lines buy a real guard against silent
upstream drift.

A closure has the same blindness as `partial`. A classmethod constructor still needs an instance to
hold `di_container`, reintroducing the state the factory already names.

**Revisit trigger:** `functools.partial` (or the call site) gains precise enough signature typing
that a contract break is caught at `add_middleware`, **or** FastStream starts accepting a pre-bound
middleware instance so no deferred factory is needed. Either removes the factory's remaining
justification.
