# Keep the `_DIMiddlewareFactory` two-class split

`_DIMiddlewareFactory` reads as a pass-through worth folding away: a one-method class whose
`__call__` binds the root container and forwards to `_DiMiddleware`. Typing it to FastStream's real
`__call__(msg, /, *, context: ContextRepo)` contract (#39) dropped the last `ty` suppressions and
made `functools.partial(_DiMiddleware, container)` viable and about ten lines shorter, so the
original "some carrier is unavoidable" argument stopped deciding. What decides instead is
type-checkability at the registration seam: `partial` types as `(*args: Any, **kwargs: Any)` and is
assignable to any protocol, so renaming `_DiMiddleware.__init__`'s `context` keyword would still
pass `ty` and fail at runtime on the first message, while the named factory turns the same break
into a type error at `broker.add_middleware(...)`. A closure is blind the same way, and a
classmethod constructor still needs an instance to hold the container. Only FastStream accepting a
pre-bound middleware instance would remove the factory's job.
