# Install the DI middleware on startup, on every broker

**Decision:** `setup_di` does not call `add_middleware` itself. It registers an `on_startup` hook
that walks `app.brokers` and adds the middleware factory to each broker that does not already
carry it.

## Why

FastStream 0.7 apps hold a list of brokers. `FastStream(*brokers)` accepts many, `app.add_broker`
appends more after construction, and `app.broker` is only `brokers[0]`. Installing on `app.broker`
at `setup_di` time therefore left every other broker without DI, and the gap was silent: the app
started, and the first message to a subscriber on another broker failed inside `FromDI` with a
missing request container and nothing pointing at the cause
([#42](https://github.com/modern-python/modern-di-faststream/issues/42)).

Iterating `app.brokers` inside `setup_di` fixes the construction-time case but still misses a
broker added afterwards, and the only remedy would be a documented ordering rule the user has to
remember. Startup is the one moment when the broker list is complete and no message has been
consumed yet, so installing there needs no rule. It is safe because FastStream builds a
subscriber's middleware stack per message from the broker config, so a middleware added in an
`on_startup` hook applies to subscribers registered before it.

The membership check exists because `on_startup` runs on every start. Without it a stopped and
restarted app would carry two copies and build two request containers per message. The check
reads `broker.config.broker_middlewares`, the same sequence FastStream itself builds the stack
from, rather than a private record of installed brokers that could drift from it.

## What changes for a reader

Between `setup_di` and startup the middleware is not yet on any broker. Nothing in this package,
its tests, or its documentation inspects a broker in that window; `TestApp` runs the startup hooks.

`setup_di` no longer requires a broker at call time. The original version of this decision kept
the `if not app.broker` guard; [#56](https://github.com/modern-python/modern-di-faststream/issues/56)
dropped it so that a broker created inside the user's own `on_startup` hook is covered, because the
broker list is read at startup anyway. Hooks run in registration order, so that hook must be
registered before `setup_di`; the install hook raises when the list is still empty when it runs,
naming both remedies, and the message-time error from `FromDI` names the other order. A broker
that a later hook adds while another broker already exists is the one case that still surfaces at
message time.

**Revisit trigger:** FastStream exposes a hook for a broker being added to an app, so the
middleware can be installed at that moment instead of on startup, **or** FastStream freezes a
subscriber's middleware stack before `on_startup` runs, which would make a startup-time install
too late.
