import typing

import faststream
from faststream import TestApp
from faststream.nats import NatsBroker, TestNatsBroker

from modern_di_faststream import FromDI, fetch_di_container
from tests.dependencies import Dependencies, SimpleCreator


TEST_SUBJECT = "test"


async def test_startup_reopens_container_across_cycles(app: faststream.FastStream) -> None:
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
