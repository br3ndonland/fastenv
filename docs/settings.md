---
icon: lucide/settings
---

# Application settings

## Starlette integration

`fastenv.StarletteConfig` extends [Starlette's `Config`](https://www.starlette.io/config/) with asynchronous loading of multiple dotenv files and TOML settings, plus configurable file error handling. It inherits Starlette's settings lookup, type casting, defaults, and environment prefixes.

Install the optional integration into your project's virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'fastenv[starlette]'
```

Create a `.env` file:

```sh
DEBUG=false
PORT=8000
ALLOWED_HOSTS=localhost,127.0.0.1
```

Load the files asynchronously, then read settings with the same calling convention as Starlette. Save this example as a Python script and run it from the directory containing `.env`:

```py
import anyio
import fastenv
from starlette.datastructures import CommaSeparatedStrings


async def load_config() -> fastenv.StarletteConfig:
    return await fastenv.StarletteConfig.load(".env")


config = anyio.run(load_config)

DEBUG = config("DEBUG", cast=bool, default=False)
PORT = config("PORT", cast=int, default=8000)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=CommaSeparatedStrings, default="localhost")
```

The script examples use `anyio.run()` to start an event loop. In an async application, await `StarletteConfig.load()` inside an async function instead. See [application startup](#application-startup) for a lifespan example.

You can also import the same class as `Config`:

```py
from fastenv.settings.starlette_config import Config
```

Starlette is an optional dependency. Install `fastenv[starlette]` before importing this class. The rest of fastenv remains usable without Starlette installed.

## Sources and precedence

The asynchronous `StarletteConfig.load()` class method creates a config instance and reads the requested files using AnyIO. It accepts `env_file`, `environ`, `env_prefix`, and `encoding` as positional or keyword arguments. The `toml_file`, `toml_table`, and `raise_exceptions` arguments are keyword-only.

| Argument | Default | Purpose |
| --- | --- | --- |
| `env_file` | `None` | A string or path-like object, or a list or tuple of paths to dotenv files. |
| `environ` | `starlette.config.environ` | The mapping used to read environment variables. |
| `env_prefix` | `""` | A prefix added to setting names before looking up values. |
| `encoding` | `"utf-8"` | The encoding used to read dotenv files. |
| `toml_file` | `None` | A string or path-like object pointing to a TOML file, read as UTF-8. |
| `toml_table` | `"project"` | The top-level TOML table to load. |
| `raise_exceptions` | `True` | Whether file loading errors are raised after being logged. |

No files are loaded unless their paths are provided. Relative paths are resolved from the current working directory. For environment-only settings, construct `StarletteConfig()` directly. Its constructor accepts only the keyword arguments `environ` and `env_prefix`, and performs no file I/O.

Values are looked up in this order, from highest to lowest priority:

1. The environment mapping.
2. Dotenv files, with later files overriding earlier files.
3. The selected TOML table.
4. The `default` passed to the setting lookup.

For example, this configuration loads base values from `pyproject.toml`, overrides them with `.env`, then overrides those values with `.env.local`. An existing environment variable overrides all three files.

```py
import anyio
import fastenv


async def load_config() -> fastenv.StarletteConfig:
    return await fastenv.StarletteConfig.load(
        env_file=[".env", ".env.local"],
        toml_file="pyproject.toml",
    )


config = anyio.run(load_config)
PORT = config("PORT", cast=int, default=8000)
```

Loading these files does not modify `os.environ` or a supplied `environ` mapping. File values belong to the config instance. This differs from [`fastenv.load_dotenv`](dotenv.md#loading-a-env-file), which sets environment variables.

## TOML settings

The integration uses Python's standard library `tomllib`, available in Python 3.11 and later. By default, it reads the `[project]` table, so application metadata can come from your existing `pyproject.toml`:

```toml
[project]
name = "example-app"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["fastenv[starlette]"]
```

```py
import anyio
import fastenv


async def load_config() -> fastenv.StarletteConfig:
    return await fastenv.StarletteConfig.load(toml_file="pyproject.toml")


config = anyio.run(load_config)

APP_NAME = config("NAME")
APP_VERSION = config("VERSION")
REQUIRES_PYTHON = config("REQUIRES-PYTHON")
DEPENDENCIES = config("DEPENDENCIES")
```

Only the table's immediate keys are converted to uppercase. Hyphens are preserved, so `requires-python` becomes `REQUIRES-PYTHON`. Native values such as integers, booleans, lists, and dictionaries keep their types when no `cast` is requested. Nested keys are preserved and nested tables are returned as dictionaries.

Use `toml_table` to select another top-level table. For example, save this as `settings.toml`:

```toml
[application]
debug = false
port = 8000

[application.database]
host = "localhost"
port = 5432
```

```py
import anyio
import fastenv


async def load_config() -> fastenv.StarletteConfig:
    return await fastenv.StarletteConfig.load(
        toml_file="settings.toml",
        toml_table="application",
    )


config = anyio.run(load_config)

DEBUG = config("DEBUG", cast=bool)
PORT = config("PORT", cast=int)
DATABASE = config("DATABASE")
# {"host": "localhost", "port": 5432}
```

Environment and dotenv values remain strings, so use `cast` when a setting needs a consistent type across sources.

## Starlette behavior

The integration inherits Starlette's handling of Boolean strings, such as `"false"`, and accepts callable casts such as `Secret` and `CommaSeparatedStrings`. Missing settings without a default raise `KeyError`, and invalid casts raise `ValueError`.

An environment prefix applies to lookups across all sources. For example, `config("DEBUG")` below reads `APP_DEBUG`:

```py
import fastenv
from starlette.datastructures import Secret

config = fastenv.StarletteConfig(
    environ={"APP_DEBUG": "false", "APP_SECRET_KEY": "example-secret"},
    env_prefix="APP_",
)

DEBUG = config("DEBUG", cast=bool)
SECRET_KEY = config("SECRET_KEY", cast=Secret)
```

With the default `starlette.config.environ` mapping, Starlette's protection against modifying environment variables after they have been read still applies. See [the Starlette comparison](comparisons.md#one-way-configuration-preference) for more detail.

## File errors

Missing, unreadable, or invalid input files are logged and raise an exception by default. To allow optional files, pass `raise_exceptions=False`. A failed source is skipped, while successfully loaded sources remain available:

```py
import anyio
import fastenv


async def load_config() -> fastenv.StarletteConfig:
    return await fastenv.StarletteConfig.load(
        env_file=[".env", ".env.local"],
        toml_file="pyproject.toml",
        raise_exceptions=False,
    )


config = anyio.run(load_config)
DEBUG = config("DEBUG", cast=bool, default=False)
```

This option only controls source loading errors. Missing required settings and invalid casts still raise exceptions when settings are read.

## Application startup

Await `StarletteConfig.load()` once during application startup to avoid reading files on each request. File I/O uses AnyIO, and setting lookups on the returned instance are synchronous. For example, load settings in a Starlette lifespan function and expose them through request state:

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import fastenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class LifespanState(TypedDict):
    config: fastenv.StarletteConfig


@asynccontextmanager
async def lifespan(_: Starlette) -> AsyncIterator[LifespanState]:
    config = await fastenv.StarletteConfig.load(".env")
    yield {"config": config}


async def homepage(request: Request) -> JSONResponse:
    config = request.state.config
    return JSONResponse({"debug": config("DEBUG", cast=bool, default=False)})


app = Starlette(routes=[Route("/", homepage)], lifespan=lifespan)
```

The server manages the event loop and calls the lifespan function, so no `anyio.run()` is needed. The same approach works with a FastAPI lifespan function. To load dotenv files into the process environment, use [`fastenv.load_dotenv`](dotenv.md#loading-a-env-file).
