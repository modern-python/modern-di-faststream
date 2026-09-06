# modern-di-faststream

A FastStream adapter over [`modern-di`](https://github.com/modern-python/modern-di): it registers a
container on a FastStream app and installs a broker middleware, so every subscriber parameter
marked with `FromDI` resolves from a container scoped to the message being handled.

## Language

A term is listed only when there is a synonym to reject, or a meaning subtle enough that code and
docs must agree on it. General programming vocabulary does not belong here, however heavily this
package uses it.

The domain terms are `modern-di`'s — `Container`, `Provider`, `Group`, `Scope`, `Resolution`,
`Override`. That project's `CONTEXT.md` is the authority for all of them; nothing here redefines
one. FastStream owns `broker`, `subscriber`, `middleware`, and `StreamMessage`, and this package
uses each in FastStream's sense. The three below are this package's own.

**Root container**:
The `Container` handed to `setup_di` and stored on the app's `ContextRepo`; `fetch_di_container`
reads it back. Its lifetime tracks the app's, reopened on startup and closed after shutdown.
_Avoid_: app container, app-scoped container — accurate but unnamed; the code calls it the root
container, and one of the two names has to win.

**Request container**:
The child container the middleware builds for one message and closes when that message is done.
It is where a `FromDI` parameter resolves.
_Avoid_: message container, per-message container. It is built per message, but its name comes
from its scope — `Scope.REQUEST` — so that a reader can match it to modern-di's scope ladder.

**Message**:
FastStream's `StreamMessage`, and this integration's whole notion of a unit of work. It is the
`Connection` in modern-di's sense — the framework object a unit of work carries — which is why
`faststream_message_provider` is a `ContextProvider` at `Scope.REQUEST` and why there is only ever
one connection type to derive a child scope from. `REQUEST` here names a scope band, never an HTTP
request; nothing in this package speaks HTTP.
