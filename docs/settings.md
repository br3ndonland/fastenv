---
icon: lucide/settings
---

# Application settings

## Pydantic integration

fastenv provides Pydantic settings models using its existing dotenv parser. It is an original implementation based on the public pydantic-settings 2.15.0 API, with [intentional differences](comparisons.md#differences-from-pydantic-settings). Neither pydantic-settings nor python-dotenv is a runtime dependency.

Install the optional integration into your project's virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'fastenv[settings]'
```

Change settings imports to `fastenv`. Continue importing models, fields, aliases, validators, and types from `pydantic`:

```py
import anyio
from pydantic import BaseModel

from fastenv import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SERVICE_",
        env_file=(".env", ".env.local"),
        env_nested_delimiter="__",
    )
    debug: bool = False
    database: Database = Database()


async def main() -> None:
    settings = await Settings.load()
    print(settings.model_dump())


anyio.run(main)
```

For example, `SERVICE_DEBUG=true` becomes a boolean. `SERVICE_DATABASE__PORT=6543` overrides the nested port. A JSON object in `SERVICE_DATABASE` can supply several nested values, and individual nested variables override its matching members.

### Sources and priority

The default order, from highest to lowest priority, is:

1. Constructor arguments.
2. Process environment variables.
3. Dotenv files, with later files overriding earlier files.
4. Secret files, with later directories overriding earlier directories.
5. Model defaults.

Mappings from different sources are merged recursively. Pydantic validates the merged input and applies field defaults. Default values are validated too. Unknown environment variables are ignored. Unknown constructor and dotenv values are rejected unless `extra="ignore"` or `extra="allow"` is configured.

Per-instance options use the same leading underscore as pydantic-settings. For example, `await Settings.load(_env_file="production.env")` selects another file, and `await Settings.load(_env_file=None)` disables dotenv loading. `await Settings.load(_env_prefix="OTHER_")` changes the prefix for that instance.

The environment and dotenv sources support case sensitivity, aliases, `AliasChoices`, `AliasPath`, prefix targets, nested delimiters and maximum splits, empty-value filtering, null markers, enum names, and JSON decoding. `NoDecode` and `ForceDecode` can be used as `Annotated` metadata. Model configuration can also be supplied through class keywords such as `class Settings(BaseSettings, env_prefix="SERVICE_")`.

### Dotenv parsing and environment isolation

Settings loading never changes `os.environ`. Files are parsed with `fastenv.parse_dotenv`, the same parser used by `fastenv.DotEnv`. This allows independent settings instances to use different files safely, including concurrent loads.

The parser deliberately follows fastenv's format:

- Shell tokenization handles quotes, comments, and whitespace-separated assignments.
- Keys preserve their spelling for case-sensitive settings lookup.
- Variables such as `${HOME}` remain literal text. There is no variable interpolation.
- Bare names without `=` are ignored. An assignment with no value produces an empty string.
- Leading and trailing whitespace and quote characters are stripped according to existing fastenv behavior.
- Invalid shell quoting raises an error.

These parsing details can differ from python-dotenv. Review files that rely on its interpolation or whitespace behavior when migrating.

`parse_dotenv` is also available without Pydantic. It returns key-value pairs. Convert them to a dictionary to keep the last value for each key:

```py
import fastenv

values = dict(fastenv.parse_dotenv("PORT=8000 LABEL='local service'"))
assert values == {"PORT": "8000", "LABEL": "local service"}
```

`DotEnv`, `load_dotenv`, and `dotenv_values` retain their existing environment mutation behavior. Use `await Settings.load()` to read settings files asynchronously through AnyIO, then validate the collected values:

```py
settings = await Settings.load()
```

This includes dotenv, JSON, TOML, pyproject files, and secret directories. Sources are processed in priority order so custom sources can inspect values from earlier sources. Parsing and Pydantic validation run after the file contents have been read. The synchronous `Settings(...)` constructor remains available for compatibility with pydantic-settings.

### Custom and file sources

Override `settings_customise_sources` to add, reorder, or remove sources. The first returned source has the highest priority. A source can be a callable returning a dictionary, or a subclass of `PydanticBaseSettingsSource` with `get_field_value` and `__call__` implementations. Source instances expose `current_state` and `settings_sources_data` while they are being evaluated.

`Settings.load()` also accepts async callable sources. A custom source class can implement `async def load(self)` to await its I/O and return a dictionary. The default source `load()` calls `__call__`, which supports synchronous in-memory sources. Custom sources that read files or use the network should implement asynchronous loading and avoid I/O in their constructors.

```py
from fastenv import BaseSettings, TomlConfigSettingsSource


class Settings(BaseSettings):
    port: int = 8000

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, toml_file="service.toml"),
            dotenv_settings,
            file_secret_settings,
        )
```

File sources are opt-in through this hook. Setting `toml_file` or `json_file` alone does not insert another source and emits a warning.

| Source | Configuration |
| --- | --- |
| `JsonConfigSettingsSource` | `json_file`, `json_file_encoding` |
| `TomlConfigSettingsSource` | `toml_file`, `toml_table_header` |
| `PyprojectTomlConfigSettingsSource` | `pyproject_toml_depth`, `pyproject_toml_table_header` |
| `SecretsSettingsSource` | `secrets_dir`, environment prefix and case settings |
| `NestedSecretsSettingsSource` | Secret directories, nested separators or subdirectories, prefix, case, size and missing-directory policies |

JSON and TOML use Python's standard library. YAML is [intentionally unsupported](comparisons.md#differences-from-pydantic-settings). The default pyproject section is `[tool.pydantic-settings]`, preserving the migration contract. Set `pyproject_toml_table_header=("tool", "fastenv")` to use `[tool.fastenv]` instead.

For dotenv files stored in S3-compatible object storage, use fastenv's [asynchronous object storage client](cloud-object-storage.md#downloading-files) to download a file before loading its path with `await Settings.load(_env_file=...)`. The client is available through `fastenv[cloud]` and does not depend on Boto3. Built-in cloud secret services are outside this integration's scope. See the [comparison with pydantic-settings](comparisons.md#differences-from-pydantic-settings).

### Application command-line arguments

fastenv does not generate or run command-line applications or provide pydantic-settings CLI APIs. Parse arguments in your application with Click or Python's standard-library `argparse`, then pass only explicitly supplied values to `Settings(**overrides)`:

```py
import argparse

from fastenv import BaseSettings


class Settings(BaseSettings):
    port: int = 8000


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=argparse.SUPPRESS)
overrides = vars(parser.parse_args())
settings = Settings(**overrides)
```

`argparse.SUPPRESS` keeps omitted options out of the mapping, allowing environment variables, files, and model defaults to supply their values. When using Click, likewise include only parameters explicitly supplied by the user. Return this mapping from a [custom source](#custom-and-file-sources) when a different priority is needed.

### Compatibility and verification

The compatibility target is the released **pydantic-settings 2.15.0** public API for environment variables, local files, secret directories, and custom sources, imported through `fastenv`. CLI APIs, YAML, cloud providers, and parser differences are documented in the [comparison with pydantic-settings](comparisons.md#differences-from-pydantic-settings). Internal module paths, private methods, and exact error text are not compatibility contracts. The fastenv package version remains available as `fastenv.__version__`.

The implementation was written from public documentation, signatures, and independently authored behavioral comparisons during development. No pydantic-settings implementation or tests were copied.

Ongoing regression checks live in the regular test suite and run through the project's [pytest workflow](contributing.md#testing-with-pytest), without installing pydantic-settings or python-dotenv. They cover settings validation, source priority, aliases, nested values, file loading, and optional dependency isolation. These tests exercise a defined set of behaviors and are not proof of exhaustive equivalence for all Pydantic types and settings configurations.

Background: [fastenv discussion 21](https://github.com/br3ndonland/fastenv/discussions/21), [pydantic-settings](https://github.com/pydantic/pydantic-settings), and the [Pydantic settings documentation](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/).

## Starlette integration

`fastenv.StarletteConfig` builds on [Starlette's `Config`](https://starlette.dev/config/). You get the same setting lookups, type casting, defaults, and environment prefixes, plus support for multiple dotenv files and TOML settings.

Install the integration in your project's virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'fastenv[starlette]'
```

Starlette is optional. The rest of fastenv works without it installed.

### Two ways to load files

You can load files when you create the config, or let an async function create it for you. Choose whichever fits the code where you're loading your settings. Either way, you read the settings with ordinary synchronous calls afterward.

#### Load files in the constructor

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

#### Load files asynchronously

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

### Sources and precedence

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

### Loading options

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

### TOML settings

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

### Starlette behavior

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

### File errors

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

### Application startup

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
