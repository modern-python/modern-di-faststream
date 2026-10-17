import contextvars
import dataclasses
import typing
from collections.abc import Awaitable, Callable

import faststream
from faststream.asgi import AsgiFastStream
from faststream.types import DecodedMessage
from modern_di import Container, Scope, integrations, providers


T_co = typing.TypeVar("T_co", covariant=True)


faststream_message_provider = providers.ContextProvider(scope=Scope.REQUEST, context_type=faststream.StreamMessage)

_ROOT_CONTAINER_KEY = "modern_di_root_container"
_request_container: contextvars.ContextVar[Container | None] = contextvars.ContextVar(
    "modern_di_request_container", default=None
)

_MISSING_REQUEST_CONTAINER = (
    "No request container for this message, so the DI middleware did not run for it. "
    "Call setup_di(app, container) on the app that owns this broker and start the app; "
    "in tests, pair the test broker with TestApp(app) in the same `async with`. "
    "A broker added by an on_startup hook is covered only if that hook was registered before setup_di."
)
_NO_BROKER_AT_STARTUP = (
    "No broker on the app when the DI middleware is installed at startup. "
    "Pass one to FastStream(...) or app.add_broker(...) before startup; "
    "an on_startup hook that adds it must be registered before setup_di, since hooks run in registration order."
)


class _DIMiddlewareFactory:
    __slots__ = ("di_container",)

    def __init__(self, di_container: Container) -> None:
        self.di_container = di_container

    def __call__(self, msg: object, /, *, context: faststream.ContextRepo) -> "_DiMiddleware":
        return _DiMiddleware(self.di_container, msg, context=context)


class _DiMiddleware(faststream.BaseMiddleware):
    def __init__(self, di_container: Container, msg: object, /, *, context: faststream.ContextRepo) -> None:
        self.di_container = di_container
        super().__init__(msg, context=context)

    async def consume_scope(
        self,
        call_next: Callable[[typing.Any], Awaitable[typing.Any]],
        msg: faststream.StreamMessage[typing.Any],
    ) -> typing.AsyncIterator[DecodedMessage]:
        match = integrations.bind(faststream_message_provider, msg)
        async with self.di_container.build_child_container(
            scope=match.scope, context=match.context
        ) as request_container:
            token = _request_container.set(request_container)
            try:
                return typing.cast(
                    typing.AsyncIterator[DecodedMessage],
                    await call_next(msg),
                )
            finally:
                _request_container.reset(token)


def fetch_di_container(app_: faststream.FastStream | AsgiFastStream) -> Container:
    return typing.cast(Container, app_.context.get(_ROOT_CONTAINER_KEY))


def setup_di(
    app: faststream.FastStream | AsgiFastStream,
    container: Container,
    *,
    manage_lifespan: bool = True,
) -> Container:
    container.add_providers(faststream_message_provider)
    app.context.set_global(_ROOT_CONTAINER_KEY, container)
    middleware_factory = _DIMiddlewareFactory(container)

    # Installed on startup rather than here so a broker added after ``setup_di`` is covered,
    # and skipped where present so a restart adds no second copy: docs/adr/0002-install-middleware-on-startup.md
    async def install_middleware() -> None:
        if not app.brokers:
            raise RuntimeError(_NO_BROKER_AT_STARTUP)
        for broker in app.brokers:
            if middleware_factory not in broker.config.broker_middlewares:
                broker.add_middleware(middleware_factory)

    app.on_startup(install_middleware)
    if manage_lifespan:
        close_registered = False

        # Appended on startup so the close runs after every after_shutdown hook registered before it.
        async def open_root() -> None:
            nonlocal close_registered
            container.open()
            if not close_registered:
                app.after_shutdown(container.close_async)
                close_registered = True

        app.on_startup(open_root)
    return container


@dataclasses.dataclass(slots=True, frozen=True)
class Dependency(typing.Generic[T_co]):
    marker: integrations.Marker[T_co]

    async def __call__(self) -> T_co:
        request_container = _request_container.get()
        if request_container is None:
            raise RuntimeError(_MISSING_REQUEST_CONTAINER)
        return self.marker.resolve(request_container)


def FromDI(  # noqa: N802
    dependency: providers.AbstractProvider[T_co] | type[T_co], *, use_cache: bool = True, cast: bool = False
) -> T_co:
    return typing.cast(
        T_co,
        faststream.Depends(dependency=Dependency(integrations.Marker(dependency)), use_cache=use_cache, cast=cast),
    )
