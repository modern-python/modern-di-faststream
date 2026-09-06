import typing

import faststream
from faststream import TestApp
from faststream.nats import NatsBroker, TestNatsBroker

from modern_di_faststream import FromDI, fetch_di_container
from tests.dependencies import Dependencies, SimpleCreator


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
