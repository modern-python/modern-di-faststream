import dataclasses
import typing
from collections.abc import Awaitable, Callable

import faststream
from faststream.asgi import AsgiFastStream
from faststream.types import DecodedMessage
from modern_di import Container, Scope, integrations, providers


T_co = typing.TypeVar("T_co", covariant=True)
P = typing.ParamSpec("P")


faststream_message_provider = providers.ContextProvider(scope=Scope.REQUEST, context_type=faststream.StreamMessage)

# Keys under which the containers live in FastStream's ``ContextRepo``. Each is
# written in one place and read in another; naming them keeps writer and reader
# in provable agreement instead of relying on two matching string literals.
_ROOT_CONTAINER_KEY = "di_container"
_REQUEST_CONTAINER_KEY = "request_container"


class _DIMiddlewareFactory:
    __slots__ = ("di_container",)

    def __init__(self, di_container: Container) -> None:
        self.di_container = di_container

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> "_DiMiddleware[P]":
        return _DiMiddleware(self.di_container, *args, **kwargs)


class _DiMiddleware(faststream.BaseMiddleware, typing.Generic[P]):
    def __init__(self, di_container: Container, *args: P.args, **kwargs: P.kwargs) -> None:
        self.di_container = di_container
        # BaseMiddleware.__init__ expects (msg, /, *, context: ContextRepo); ParamSpec forwarding can't prove that.
        super().__init__(*args, **kwargs)  # ty: ignore[invalid-argument-type]

    async def consume_scope(
        self,
        call_next: Callable[[typing.Any], Awaitable[typing.Any]],
        msg: faststream.StreamMessage[typing.Any],
    ) -> typing.AsyncIterator[DecodedMessage]:
        match = integrations.bind(faststream_message_provider, msg)
        async with self.di_container.build_child_container(
            scope=match.scope, context=match.context
        ) as request_container:
            with self.context.scope(_REQUEST_CONTAINER_KEY, request_container):
                return typing.cast(
                    typing.AsyncIterator[DecodedMessage],
                    await call_next(msg),
                )


def fetch_di_container(app_: faststream.FastStream | AsgiFastStream) -> Container:
    return typing.cast(Container, app_.context.get(_ROOT_CONTAINER_KEY))


def setup_di(
    app: faststream.FastStream | AsgiFastStream,
    container: Container,
) -> Container:
    if not app.broker:
        msg = "Broker must be defined to setup DI"
        raise RuntimeError(msg)

    container.add_providers(faststream_message_provider)
    app.context.set_global(_ROOT_CONTAINER_KEY, container)
    # FastStream's lifecycle is callback-based, so the root container can't be
    # wrapped in ``async with``. Reopen it on startup (before the broker consumes)
    # to pair with the shutdown close, so a broker restart works instead of
    # raising ContainerClosedError. Reopening an already-open container is a no-op.
    app.on_startup(container.open)
    app.after_shutdown(container.close_async)
    # _DIMiddlewareFactory.__call__ ParamSpec doesn't structurally match BrokerMiddleware[Any, Any].
    app.broker.add_middleware(_DIMiddlewareFactory(container))  # ty: ignore[invalid-argument-type]
    return container


@dataclasses.dataclass(slots=True, frozen=True)
class Dependency(typing.Generic[T_co]):
    marker: integrations.Marker[T_co]

    async def __call__(self, context: faststream.ContextRepo) -> T_co:
        request_container: Container = context.get(_REQUEST_CONTAINER_KEY)
        return self.marker.resolve(request_container)


def FromDI(  # noqa: N802
    dependency: providers.AbstractProvider[T_co] | type[T_co], *, use_cache: bool = True, cast: bool = False
) -> T_co:
    return typing.cast(
        T_co,
        faststream.Depends(dependency=Dependency(integrations.Marker(dependency)), use_cache=use_cache, cast=cast),
    )
