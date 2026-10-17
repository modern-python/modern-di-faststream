import typing
from collections.abc import Callable
from unittest import mock

import anyio.to_thread
import faststream
import pytest
from faststream import TestApp
from faststream.asgi import AsgiFastStream
from faststream.nats import NatsBroker, TestNatsBroker
from modern_di import Container

from modern_di_faststream import FromDI, fetch_di_container, setup_di
from tests.dependencies import Dependencies, Finalizable, SimpleCreator


TEST_SUBJECT = "test"


async def test_startup_reopens_container_across_cycles(app: faststream.FastStream) -> None:
    """INVARIANT: a second app startup reopens the same root container rather than leaving it closed.

    Broken by dropping the ``app.on_startup(container.open)`` half of the pairing in ``setup_di``,
    or by making ``after_shutdown`` do anything a reopen cannot undo. FastStream's lifecycle is
    callback-based, so the root container cannot be held in an ``async with`` that would restore
    it; the pairing is the only thing standing between a broker restart and a
    ``ContainerClosedError`` on the first message of the second run, which no single-cycle test
    would ever reach.
    """
    broker = typing.cast(NatsBroker, app.broker)
    container = fetch_di_container(app)

    @broker.subscriber(TEST_SUBJECT)
    async def index_subscriber(
        message: str,
        instance: typing.Annotated[SimpleCreator, FromDI(Dependencies.app_factory)],
    ) -> None:
        assert message == "test"
        assert isinstance(instance, SimpleCreator)

    async with TestNatsBroker(broker) as br:
        # First lifecycle: after_shutdown closes the root container.
        async with TestApp(app):
            await br.publish("test", TEST_SUBJECT)
        assert container.closed

        # Second lifecycle: on_startup must reopen the same container, so the
        # middleware can build a request child instead of raising ContainerClosedError.
        async with TestApp(app):
            assert not container.closed
            await br.publish("test", TEST_SUBJECT)


def _unmanaged_app() -> tuple[faststream.FastStream, NatsBroker, Container, list[Finalizable]]:
    broker = NatsBroker()
    app = faststream.FastStream(broker)
    container = setup_di(app, Container(groups=[Dependencies]), manage_lifespan=False)
    request_instances: list[Finalizable] = []

    @broker.subscriber(TEST_SUBJECT)
    async def index_subscriber(
        message: str,
        app_instance: typing.Annotated[Finalizable, FromDI(Dependencies.app_finalizable)],
        request_instance: typing.Annotated[Finalizable, FromDI(Dependencies.request_finalizable)],
    ) -> None:
        assert message == "test"
        assert app_instance is container.resolve_provider(Dependencies.app_finalizable)
        request_instances.append(request_instance)

    return app, broker, container, request_instances


async def test_manage_lifespan_false_leaves_the_root_open_after_shutdown() -> None:
    app, broker, container, _ = _unmanaged_app()

    async with TestNatsBroker(broker) as br, TestApp(app):
        await br.publish("test", TEST_SUBJECT)

    assert not container.closed
    assert container.resolve_provider(Dependencies.app_finalizable).finalized == 0


async def test_manage_lifespan_false_still_builds_and_closes_the_request_container() -> None:
    app, broker, _, request_instances = _unmanaged_app()

    async with TestNatsBroker(broker) as br, TestApp(app):
        await br.publish("test", TEST_SUBJECT)

    assert [instance.finalized for instance in request_instances] == [1]


async def test_manage_lifespan_false_lets_the_user_own_the_root() -> None:
    app, broker, container, _ = _unmanaged_app()

    async with container:
        async with TestNatsBroker(broker) as br, TestApp(app):
            await br.publish("test", TEST_SUBJECT)
        app_instance = container.resolve_provider(Dependencies.app_finalizable)
        assert app_instance.finalized == 0

    assert container.closed
    assert app_instance.finalized == 1


class _CloseCountingContainer(Container):
    close_calls = 0

    async def close_async(self) -> None:
        self.close_calls += 1
        await super().close_async()


def _setup_on_faststream(broker: NatsBroker, container: Container) -> faststream.FastStream | AsgiFastStream:
    app = faststream.FastStream(broker)
    setup_di(app, container)
    return app


def _setup_on_asgi(broker: NatsBroker, container: Container) -> faststream.FastStream | AsgiFastStream:
    app = AsgiFastStream(broker)
    setup_di(app, container)
    return app


def _setup_then_as_asgi(broker: NatsBroker, container: Container) -> faststream.FastStream | AsgiFastStream:
    app = faststream.FastStream(broker)
    setup_di(app, container)
    return app.as_asgi()


@pytest.mark.parametrize("build_app", [_setup_on_faststream, _setup_on_asgi, _setup_then_as_asgi])
async def test_after_shutdown_hook_registered_after_setup_di_sees_the_open_root(
    build_app: Callable[[NatsBroker, Container], faststream.FastStream | AsgiFastStream],
) -> None:
    broker = NatsBroker()
    container = _CloseCountingContainer(groups=[Dependencies])
    app = build_app(broker, container)
    seen: list[tuple[Finalizable, int]] = []

    @app.after_shutdown
    def user_hook() -> None:
        instance = container.resolve_provider(Dependencies.app_finalizable)
        seen.append((instance, instance.finalized))

    for cycle in (1, 2):
        async with TestNatsBroker(broker), TestApp(app):
            pass
        assert [(instance.finalized, at_hook) for instance, at_hook in seen] == [(1, 0)] * cycle
        assert container.closed
        assert container.close_calls == cycle


async def test_startup_and_shutdown_run_no_worker_thread(
    app: faststream.FastStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_sync = mock.Mock(wraps=anyio.to_thread.run_sync)
    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync)
    broker = typing.cast(NatsBroker, app.broker)

    async with TestNatsBroker(broker), TestApp(app):
        pass

    assert run_sync.call_count == 0
