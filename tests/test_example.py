import typing

from faststream import TestApp
from faststream.nats import NatsBroker, TestNatsBroker

from examples.app import app


async def test_example_resolves_and_greets() -> None:
    broker = typing.cast(NatsBroker, app.broker)
    async with TestNatsBroker(broker) as br, TestApp(app):
        result = await br.request("world", "greetings")
        reply = await result.decode()
    assert reply == "Hello, world!"
