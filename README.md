# modern-di-faststream

[![PyPI version](https://img.shields.io/pypi/v/modern-di-faststream.svg)](https://pypi.org/project/modern-di-faststream/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/modern-di-faststream.svg)](https://pypi.org/project/modern-di-faststream/)
[![Downloads](https://img.shields.io/pypi/dm/modern-di-faststream.svg)](https://pypistats.org/packages/modern-di-faststream)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/modern-python/modern-di-faststream/actions/workflows/ci.yml)
[![CI](https://github.com/modern-python/modern-di-faststream/actions/workflows/ci.yml/badge.svg)](https://github.com/modern-python/modern-di-faststream/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/modern-python/modern-di-faststream.svg)](https://github.com/modern-python/modern-di-faststream/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/modern-python/modern-di-faststream)](https://github.com/modern-python/modern-di-faststream/stargazers)
[![Context7](https://img.shields.io/badge/Context7-docs-blue)](https://context7.com/modern-python/modern-di-faststream)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)

[Modern-DI](https://github.com/modern-python/modern-di) integration for [FastStream](https://faststream.ag2.ai).

## Installation

```bash
uv add modern-di-faststream      # or: pip install modern-di-faststream
```

## Usage

`setup_di` registers the container and installs a broker middleware that builds a per-message child container; `FromDI` resolves a provider (or type) into a subscriber parameter.

```python
import dataclasses

import faststream
from faststream.nats import NatsBroker
from modern_di import Container, Group, Scope, providers
from modern_di_faststream import FromDI, setup_di


@dataclasses.dataclass(kw_only=True)
class Settings:
    debug: bool = True


@dataclasses.dataclass(kw_only=True)
class GreetingHandler:
    settings: Settings  # auto-injected by type


class Dependencies(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings)
    handler = providers.Factory(scope=Scope.REQUEST, creator=GreetingHandler)


broker = NatsBroker()
app = faststream.FastStream(broker)
container = Container(groups=[Dependencies], validate=True)
setup_di(app, container)


@broker.subscriber("greetings")
async def handle(name: str, handler: GreetingHandler = FromDI(Dependencies.handler)) -> None:
    print(name, handler.settings.debug)
```

The current `StreamMessage` is resolvable within DI via the pre-built `faststream_message_provider` context provider.

## API

- `setup_di(app, container)` — stores the container in the app context, registers a shutdown hook, and adds the DI middleware to the broker
- `FromDI(dependency, *, use_cache=True, cast=False)` — FastStream `Depends` that resolves a provider (or type) from the per-message child container
- `fetch_di_container(app)` — returns the app-scoped container from the app context
- `faststream_message_provider` — `ContextProvider` for the current `faststream.StreamMessage`

## 📦 [PyPI](https://pypi.org/project/modern-di-faststream)

## 📝 [License](LICENSE)

## Part of `modern-python`

Browse the full list of templates and libraries in
[`modern-python`](https://github.com/modern-python) — see the org profile for the categorized index.

## modern-di ecosystem

Built on [`modern-di`](https://github.com/modern-python/modern-di), a dependency-injection framework with IoC container and scopes. Integrations:

- [`modern-di-fastapi`](https://github.com/modern-python/modern-di-fastapi) — FastAPI
- [`modern-di-litestar`](https://github.com/modern-python/modern-di-litestar) — Litestar
- [`modern-di-faststream`](https://github.com/modern-python/modern-di-faststream) — this package
- [`modern-di-typer`](https://github.com/modern-python/modern-di-typer) — Typer
- [`modern-di-pytest`](https://github.com/modern-python/modern-di-pytest) — pytest

