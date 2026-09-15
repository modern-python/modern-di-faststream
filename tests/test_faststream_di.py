import typing

import faststream
import pytest
from faststream import TestApp
from faststream.nats import NatsBroker, TestNatsBroker
from modern_di import Container

import modern_di_faststream
from modern_di_faststream import FromDI
from modern_di_faststream.main import _DIMiddlewareFactory
from tests.dependencies import Dependencies, DependentCreator, SimpleCreator


TEST_SUBJECT = "test"


async def test_factories(app: faststream.FastStream) -> None:
    broker = typing.cast(NatsBroker, app.broker)

    @broker.subscriber(TEST_SUBJECT)
    async def index_subscriber(
        message: str,
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
        request_factory_instance: typing.Annotated[DependentCreator, FromDI(Dependencies.request_factory)],
    ) -> None:
        assert message == "test"
        assert isinstance(app_factory_instance, SimpleCreator)
        assert isinstance(request_factory_instance, DependentCreator)
        assert request_factory_instance.dep1 is not app_factory_instance

    async with TestNatsBroker(broker) as br, TestApp(app):
        await br.publish("test", TEST_SUBJECT)


async def test_context_adapter(app: faststream.FastStream) -> None:
    broker = typing.cast(NatsBroker, app.broker)

    @broker.subscriber(TEST_SUBJECT)
    async def index_subscriber(
        message_is_processed: typing.Annotated[bool, FromDI(Dependencies.message_is_processed)],
    ) -> None:
        assert message_is_processed is False

    async with TestNatsBroker(broker) as br, TestApp(app):
        result = await br.request(None, TEST_SUBJECT)
        result_str = await result.decode()
        assert result_str == b""


async def test_app_without_broker() -> None:
    with pytest.raises(RuntimeError, match="Broker must be defined to setup DI"):
        modern_di_faststream.setup_di(faststream.FastStream(), container=Container())


def test_fetch_di_container(app: faststream.FastStream) -> None:
    di_container = modern_di_faststream.fetch_di_container(app)
    assert isinstance(di_container, Container)


def _app_with_two_brokers(*, add_second_after_setup: bool) -> tuple[faststream.FastStream, NatsBroker, NatsBroker]:
    first, second = NatsBroker(), NatsBroker()
    app_ = faststream.FastStream(first) if add_second_after_setup else faststream.FastStream(first, second)
    modern_di_faststream.setup_di(app_, container=Container(groups=[Dependencies]))
    if add_second_after_setup:
        app_.add_broker(second)
    return app_, first, second


def _subscribe_resolving(broker: NatsBroker, subject: str, resolved: list[SimpleCreator]) -> None:
    @broker.subscriber(subject)
    async def subscriber(instance: typing.Annotated[SimpleCreator, FromDI(Dependencies.app_factory)]) -> None:
        resolved.append(instance)


@pytest.mark.parametrize("add_second_after_setup", [False, True], ids=["at-construction", "after-setup_di"])
async def test_di_resolves_on_every_broker(add_second_after_setup: bool) -> None:
    """INVARIANT: a ``FromDI`` parameter resolves on every broker of the app, not only ``app.broker``.

    Broken by installing the middleware on ``app.broker`` alone, or by installing it when
    ``setup_di`` runs instead of on startup: FastStream 0.7 apps hold a list of brokers, and
    ``app.add_broker`` may append to it after ``setup_di`` returned. Either regression is silent at
    setup and surfaces as a missing request container on the first message to the other broker.
    """
    app_, first, second = _app_with_two_brokers(add_second_after_setup=add_second_after_setup)
    resolved: list[SimpleCreator] = []
    _subscribe_resolving(first, "first", resolved)
    _subscribe_resolving(second, "second", resolved)

    async with TestNatsBroker(first, second) as (first_test, second_test), TestApp(app_):
        await first_test.publish(None, "first")
        await second_test.publish(None, "second")

    assert [type(instance) for instance in resolved] == [SimpleCreator, SimpleCreator]


async def test_middleware_is_installed_once_per_broker_across_restarts() -> None:
    """INVARIANT: each broker carries exactly one DI middleware however many times the app starts.

    Broken by a startup hook that adds the middleware unconditionally. Every start after the first
    would then add another copy, and each message would build one request container per copy,
    with only the innermost visible to ``FromDI``.
    """
    app_, first, second = _app_with_two_brokers(add_second_after_setup=False)

    async with TestNatsBroker(first, second), TestApp(app_):
        pass
    async with TestNatsBroker(first, second), TestApp(app_):
        pass

    for broker in (first, second):
        installed = [m for m in broker.config.broker_middlewares if isinstance(m, _DIMiddlewareFactory)]
        assert len(installed) == 1


async def test_from_di_without_setup_di_raises_clear_error() -> None:
    """INVARIANT: a ``FromDI`` parameter on an app that never called ``setup_di`` names the fix.

    Without ``setup_di`` no middleware runs, so no request container is in the ``ContextRepo``.
    Broken by resolving against whatever ``context.get`` returns: the failure is then an
    ``AttributeError`` on ``None`` deep in the resolve, which says nothing about ``setup_di``.
    """
    broker = NatsBroker()
    app_ = faststream.FastStream(broker)
    resolved: list[SimpleCreator] = []
    _subscribe_resolving(broker, TEST_SUBJECT, resolved)

    async with TestNatsBroker(broker) as br, TestApp(app_):
        with pytest.raises(RuntimeError, match=r"setup_di\(app, container\)"):
            await br.publish(None, TEST_SUBJECT)

    assert resolved == []
