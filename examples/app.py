# Minimal modern-di + faststream example.
# Run for real (needs a running NATS broker):  faststream run examples.app:app
import dataclasses

import faststream
from faststream.nats import NatsBroker
from modern_di import Container, Group, Scope, providers

from modern_di_faststream import FromDI, setup_di


@dataclasses.dataclass(kw_only=True)
class Settings:
    greeting: str = "Hello"


@dataclasses.dataclass(kw_only=True)
class GreetingService:
    settings: Settings  # auto-injected by type

    def greet(self, name: str) -> str:
        return f"{self.settings.greeting}, {name}!"


class Dependencies(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings)
    service = providers.Factory(scope=Scope.REQUEST, creator=GreetingService)


broker = NatsBroker()
app = faststream.FastStream(broker)
container = Container(groups=[Dependencies], validate=True)
setup_di(app, container)


@broker.subscriber("greetings")
async def greet(name: str, service: GreetingService = FromDI(Dependencies.service)) -> str:  # noqa: B008
    return service.greet(name)
