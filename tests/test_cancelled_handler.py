import logging
import typing

import anyio
import faststream
import pytest
from faststream import TestApp
from faststream.nats import NatsBroker, TestNatsBroker
from modern_di import Container, Group, Scope, providers

from modern_di_faststream import FromDI, main, setup_di


class _First: ...


class _Second: ...


def _app(log: list[str], *, second_finalizer_delay: float) -> faststream.FastStream:
    async def finalize_first(_: _First) -> None:
        await anyio.sleep(0.01)
        log.append("first")

    async def finalize_second(_: _Second) -> None:
        await anyio.sleep(second_finalizer_delay)
        log.append("second")

    class G(Group):
        first = providers.Factory(
            scope=Scope.REQUEST, creator=_First, cache=providers.CacheSettings(finalizer=finalize_first)
        )
        second = providers.Factory(
            scope=Scope.REQUEST, creator=_Second, cache=providers.CacheSettings(finalizer=finalize_second)
        )

    broker = NatsBroker()
    app = faststream.FastStream(broker)
    setup_di(app, Container(groups=[G]))

    @broker.subscriber("slow")
    async def slow(
        message: str,
        first: typing.Annotated[_First, FromDI(_First)],
        second: typing.Annotated[_Second, FromDI(_Second)],
    ) -> None:
        assert message == "go"
        assert isinstance(first, _First)
        assert isinstance(second, _Second)
        await anyio.sleep_forever()

    return app


async def _cancel_a_running_handler(app: faststream.FastStream) -> None:
    broker = typing.cast(NatsBroker, app.broker)
    async with TestNatsBroker(broker) as test_broker, TestApp(app):

        async def publish() -> None:
            with anyio.move_on_after(0.05):
                await test_broker.publish("go", "slow")

        # Its own task keeps the cancellation out of the test's frame, where 3.11 coverage loses a line.
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(publish)


async def test_a_cancelled_handler_still_runs_every_request_finalizer() -> None:
    log: list[str] = []

    await _cancel_a_running_handler(_app(log, second_finalizer_delay=0.01))

    assert log == ["second", "first"]


async def test_a_hung_request_finalizer_is_abandoned_after_the_bound(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(main, "_CHILD_CLOSE_TIMEOUT", 0.05)
    caplog.set_level(logging.WARNING, logger=main.__name__)
    log: list[str] = []

    await _cancel_a_running_handler(_app(log, second_finalizer_delay=10))

    assert log == []
    assert [record.getMessage() for record in caplog.records if record.name == main.__name__] == [
        "Closing the request container did not finish within 0.05 s; its remaining finalizers did not run"
    ]
