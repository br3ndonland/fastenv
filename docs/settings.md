---
icon: lucide/settings
---

# Application settings

## Starlette integration

`fastenv.StarletteConfig` builds on [Starlette's `Config`](https://starlette.dev/config/). You get the same setting lookups, type casting, defaults, and environment prefixes, plus support for multiple dotenv files and TOML settings.

Install the integration in your project's virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'fastenv[starlette]'
```

Starlette is optional. The rest of fastenv works without it installed.

## Two ways to load files

You can load files when you create the config, or let an async function create it for you. Choose whichever fits the code where you're loading your settings. Either way, you read the settings with ordinary synchronous calls afterward.

### Load files in the constructor

If you're writing a script or setting up configuration before an event loop starts, pass your file paths to `StarletteConfig`. This works much like Starlette's own `Config`, but also accepts a list or tuple of files.

For example, start with a `.env` file:

```sh
DEBUG=false
PORT=8000
ALLOWED_HOSTS=localhost,127.0.0.1
```

Then load it and read your settings:

```py
import fastenv
from starlette.datastructures import CommaSeparatedStrings

config = fastenv.StarletteConfig(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
PORT = config("PORT", cast=int, default=8000)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=CommaSeparatedStrings, default="localhost")
```

To add local overrides, create `.env.local` and pass both paths:

```py
import fastenv

config = fastenv.StarletteConfig(env_file=[".env", ".env.local"])
```

The constructor waits until loading finishes. It uses `anyio.run()` to run the same async file reader used by the async option below.

### Load files asynchronously

If you're already inside an async function, use `await StarletteConfig.load(...)`. It creates a new config instance and loads the files without blocking the event loop:

```py
import fastenv


async def load_settings() -> fastenv.StarletteConfig:
    config = await fastenv.StarletteConfig.load(env_file=[".env", ".env.local"])
    port = config("PORT", cast=int, default=8000)
    print(f"Using port {port}")
    return config
```

You don't need to create an instance first. `load()` is a class method that returns the populated config. It accepts the same arguments as the constructor.

Use this option in a Starlette or FastAPI lifespan function, an async task, or a notebook with an active event loop. Passing files to the constructor in that context raises `RuntimeError`, because `anyio.run()` cannot start another event loop in the same thread. See [application startup](#application-startup) for a complete lifespan example.

If all your settings come from the environment, `StarletteConfig()` works in either context. Without file arguments, it doesn't read files or start an event loop.

## Sources and precedence

An environment variable always wins over a file value. Within a load, settings are looked up in this order:

1. The environment mapping.
2. Dotenv files, with later files overriding earlier files.
3. The selected TOML table.
4. The `default` passed to the setting lookup.

For example, this loads base values from `pyproject.toml`, then applies `.env` and `.env.local`. An existing environment variable overrides all three:

```py
import fastenv

config = fastenv.StarletteConfig(
    env_file=[".env", ".env.local"],
    toml_file="pyproject.toml",
)
PORT = config("PORT", cast=int, default=8000)
```

In async code, pass those same arguments to `await StarletteConfig.load(...)`.

File values belong to the config instance. Loading them doesn't change `os.environ` or a supplied `environ` mapping. This differs from [`fastenv.load_dotenv`](dotenv.md#loading-a-env-file), which sets environment variables.

## Loading options

The constructor and `load()` both accept these arguments. The first four can be positional or keyword arguments, matching Starlette's calling convention. The TOML and error-handling options are keyword-only.

| Argument | Default | Purpose |
| --- | --- | --- |
| `env_file` | `None` | One dotenv path, or a list or tuple of paths. Strings and path-like objects are accepted. |
| `environ` | `starlette.config.environ` | The mapping used to read environment variables. |
| `env_prefix` | `""` | A prefix added to setting names before looking up values. |
| `encoding` | `"utf-8"` | The encoding used to read dotenv files. |
| `toml_file` | `None` | A TOML file to read as UTF-8. |
| `toml_table` | `"project"` | The top-level TOML table to load. |
| `raise_exceptions` | `True` | Whether file loading errors are raised after being logged. |

Only files you name are loaded. Relative paths start from the current working directory.

You can also import the class directly from its module:

```py
from fastenv.settings.starlette_config import StarletteConfig
```

## TOML settings

You can use your existing `pyproject.toml` for application metadata. By default, the config reads its `[project]` table:

```toml
[project]
name = "example-app"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["fastenv[starlette]"]
```

```py
import fastenv

config = fastenv.StarletteConfig(toml_file="pyproject.toml")

APP_NAME = config("NAME")
APP_VERSION = config("VERSION")
REQUIRES_PYTHON = config("REQUIRES-PYTHON")
DEPENDENCIES = config("DEPENDENCIES")
```

The table's immediate keys become uppercase. Hyphens stay in place, so `requires-python` becomes `REQUIRES-PYTHON`. Values keep their native types, including integers, booleans, lists, and dictionaries. Nested keys stay as written in the file.

To use another top-level table, pass `toml_table`. For example, save this as `settings.toml`:

```toml
[application]
debug = false
port = 8000

[application.database]
host = "localhost"
port = 5432
```

```py
import fastenv

config = fastenv.StarletteConfig(
    toml_file="settings.toml",
    toml_table="application",
)

DEBUG = config("DEBUG", cast=bool)
PORT = config("PORT", cast=int)
DATABASE = config("DATABASE")
# {"host": "localhost", "port": 5432}
```

Environment and dotenv values are strings. Use `cast` when you want a consistent type regardless of which source supplies a setting. TOML parsing uses Python's standard library `tomllib`, available in Python 3.11 and later.

## Starlette behavior

Settings lookups work as they do in Starlette. For example, `cast=bool` recognizes strings like `"false"`, and casts can be callables such as `Secret` or `CommaSeparatedStrings`. Missing settings without a default raise `KeyError`. Invalid casts raise `ValueError`.

An environment prefix applies across all sources. Here, `config("DEBUG")` reads `APP_DEBUG`:

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

The default `starlette.config.environ` mapping also keeps Starlette's protection against changing environment variables after they've been read. See [the Starlette comparison](comparisons.md#one-way-configuration-preference) for details.

## File errors

By default, a missing, unreadable, or invalid file is logged and raises an exception. If some files are optional, pass `raise_exceptions=False` to log the error and skip the failed source:

```py
import fastenv

config = fastenv.StarletteConfig(
    env_file=[".env", ".env.local"],
    toml_file="pyproject.toml",
    raise_exceptions=False,
)
DEBUG = config("DEBUG", cast=bool, default=False)
```

The async factory accepts the same option. Successfully loaded sources remain available. Missing required settings and invalid casts still raise exceptions when you read them.

## Application startup

A lifespan function is a good place to load settings once, before your application starts handling requests. Since the server already has an event loop running, use the async factory:

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

The server calls the lifespan function for you. The same approach works with FastAPI. If you want to load dotenv files into the process environment instead, use [`fastenv.load_dotenv`](dotenv.md#loading-a-env-file).
