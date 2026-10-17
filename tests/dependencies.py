import dataclasses
import typing

from faststream import StreamMessage
from modern_di import Group, Scope, providers


@dataclasses.dataclass(kw_only=True, slots=True)
class SimpleCreator:
    dep1: str


@dataclasses.dataclass(kw_only=True, slots=True)
class DependentCreator:
    dep1: SimpleCreator


@dataclasses.dataclass(kw_only=True, slots=True)
class Finalizable:
    finalized: int = 0

    def finalize(self) -> None:
        self.finalized += 1


def fetch_message_is_processed_from_request(message: StreamMessage[typing.Any] | None = None) -> bool:
    return message.processed if message else False


class Dependencies(Group):
    app_factory = providers.Factory(creator=SimpleCreator, kwargs={"dep1": "original"})
    request_factory = providers.Factory(scope=Scope.REQUEST, creator=DependentCreator, bound_type=None)
    action_factory = providers.Factory(scope=Scope.ACTION, creator=DependentCreator, bound_type=None)
    message_is_processed = providers.Factory(scope=Scope.REQUEST, creator=fetch_message_is_processed_from_request)
    app_finalizable = providers.Factory(
        scope=Scope.APP,
        creator=Finalizable,
        bound_type=None,
        cache=providers.CacheSettings(finalizer=Finalizable.finalize),
    )
    request_finalizable = providers.Factory(
        scope=Scope.REQUEST,
        creator=Finalizable,
        bound_type=None,
        cache=providers.CacheSettings(finalizer=Finalizable.finalize),
    )
