---
icon: lucide/settings
---

# Application settings

## Pydantic integration

fastenv provides the settings models you may know from [pydantic-settings](https://github.com/pydantic/pydantic-settings). You describe your settings as a Pydantic model, and fastenv fills it in from environment variables, dotenv files, and secret files. Pydantic then validates the result and converts each value to the type you asked for.

The API follows pydantic-settings 2.15.0, with fastenv's own dotenv parser in place of python-dotenv and a few [intentional differences](comparisons.md#differences-from-pydantic-settings).

Install the integration in your project's virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'fastenv[settings]'
```

Pydantic is optional. The rest of fastenv works without it installed. The extra installs Pydantic itself, but not pydantic-settings or python-dotenv.

### Getting started

Let's start with a `.env` file:

```sh
SERVICE_DEBUG=true
SERVICE_ALLOWED_HOSTS='["localhost", "127.0.0.1"]'
SERVICE_DATABASE__PORT=6543
```

Next, describe the settings you expect. Settings classes come from `fastenv`. Models, fields, aliases, validators, and types still come from `pydantic`:

```py
from pydantic import BaseModel

from fastenv import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SERVICE_",
        env_file=".env",
        env_nested_delimiter="__",
    )
    debug: bool = False
    allowed_hosts: list[str] = ["localhost"]
    database: Database = Database()


settings = Settings()
settings.debug
# True
settings.allowed_hosts
# ['localhost', '127.0.0.1']
settings.database
# Database(host='localhost', port=6543)
```

Every value in the file is a string, and every value on the model has the type you declared. `SERVICE_DEBUG=true` became a Boolean, the JSON array became a list, and `SERVICE_DATABASE__PORT` reached into the nested `Database` model while `host` kept its default.

If a value can't be converted, such as `SERVICE_DEBUG=maybe`, Pydantic raises a `ValidationError` that names the field. You find out at startup, instead of later when the setting is used.

### Two ways to load settings

You can create the model directly, or let an async class method create it for you. Both read the same sources and return the same validated settings.

`Settings()` reads files right away, as it does in pydantic-settings. It works anywhere, including inside an async function, but the event loop has to wait while the files are read.

If you're already inside an async function, use `await Settings.load()`. It reads the files in [AnyIO worker threads](https://anyio.readthedocs.io/en/stable/threads.html), so the event loop stays free:

```py
import anyio


async def main() -> None:
    settings = await Settings.load()
    print(settings.database.port)
    # 6543


anyio.run(main)
```

`load()` accepts the same arguments as the constructor. A FastAPI or Starlette lifespan function is a good place for it, as shown in the [quickstart](index.md#quickstart).

Files are read each time you create or load settings. To pick up a changed file, load the settings again.

### Sources and priority

When the same setting shows up in more than one place, the source highest on this list wins:

1. Arguments passed to `Settings(...)` or `Settings.load(...)`.
2. Environment variables.
3. Dotenv files, with later files overriding earlier files.
4. Secret files, with later directories overriding earlier directories.
5. Defaults on the model.

With the `.env` file above, an environment variable beats the file, and an argument beats both:

```py
import os

os.environ["SERVICE_DATABASE__PORT"] = "7000"

Settings().database.port
# 7000
Settings(debug=False).debug
# False
```

Nested models are merged across sources, not replaced. In this example, the port comes from the environment while `host` still comes from the model default.

Loading settings never changes `os.environ`. File values belong to the settings instance, so separate instances can read different files, even at the same time. This differs from [`fastenv.load_dotenv`](dotenv.md#loading-a-env-file), which sets environment variables.

Secret files are plain files named after a field, each holding a single value, the way Docker and Kubernetes mount secrets. Point `secrets_dir` at the directory, such as `secrets_dir="/run/secrets"`, and a file named `api_key` supplies the `api_key` field.

To change an option for one instance, pass it with a leading underscore, as in pydantic-settings:

```py
Settings(_env_file=".env.production")  # read a different file
Settings(_env_file=None)  # skip dotenv files
```

One thing to watch for: a name in a dotenv file that doesn't match a field is rejected, just like an unknown argument. If you share your `.env` file with other tools, add `extra="ignore"` to the model config. Unknown environment variables are always ignored.

### Naming settings

By default, a field named `debug` is read from `DEBUG`, in any letter case. These options change where fastenv looks and how it reads what it finds. They apply to environment variables and dotenv files alike:

- `env_prefix` adds a prefix to each name, so `env_prefix="SERVICE_"` reads `SERVICE_DEBUG`.
- `env_prefix_target` chooses whether the prefix applies to field names (`"variable"`, the default), aliases (`"alias"`), or both (`"all"`).
- `case_sensitive` matches names exactly when `True`.
- `env_nested_delimiter` splits names into nested fields, so `"__"` lets `DATABASE__PORT` set `database.port`.
- `env_nested_max_split` limits how many times a name is split, for nested field names that contain the delimiter.
- `env_ignore_empty` treats empty values as missing, so the default applies.
- `env_parse_none_str` names a marker, such as `"null"`, that becomes `None`.
- `env_parse_enums` accepts enum member names, such as `RED` for `Color.RED`.

Lists, dictionaries, and nested models are decoded from JSON. A JSON object in `SERVICE_DATABASE` can supply several nested values at once, and individual variables such as `SERVICE_DATABASE__PORT` override its members. If you'd like to parse a value yourself in a validator, annotate the field with `NoDecode` to get the raw string. `ForceDecode` does the opposite when `enable_decoding=False` turns decoding off for the model.

To give a field another name, use Pydantic's `validation_alias`. It accepts a single name, an `AliasChoices` with several names to try in order, or an `AliasPath` into a JSON value. Aliases are used as written, without the prefix:

```py
from pydantic import AliasChoices, Field

from fastenv import BaseSettings


class Settings(BaseSettings, env_prefix="SERVICE_"):
    debug: bool = False
    port: int = Field(default=8000, validation_alias=AliasChoices("PORT", "HTTP_PORT"))
```

Here, `debug` is read from `SERVICE_DEBUG` and `port` from `PORT` or `HTTP_PORT`. The example also shows that options can be passed as class keywords instead of `model_config`.

### Dotenv parsing

Dotenv files are parsed with `fastenv.parse_dotenv`, the same parser behind [`fastenv.DotEnv`](environment.md). If you're used to python-dotenv, a few details are different:

- Values are split the way a shell would split them. Quotes, comments, and several assignments on one line all work.
- Names keep their letter case, which matters if you set `case_sensitive=True`.
- There's no variable interpolation. `${HOME}` stays as the literal text `${HOME}`.
- A bare name without `=` is skipped, and `NAME=` gives an empty string.
- Whitespace and quote characters around a value are stripped.
- Mismatched quotes raise an error.

If your files rely on python-dotenv's interpolation or whitespace handling, give them a quick review when you migrate.

`parse_dotenv` works on its own too, with or without Pydantic. It returns key-value pairs, so wrap it in `dict()` to keep the last value for each name:

```py
import fastenv

dict(fastenv.parse_dotenv("PORT=8000 LABEL='local service'"))
# {'PORT': '8000', 'LABEL': 'local service'}
```

### Custom and file sources

The default sources are only a starting point. Override `settings_customise_sources` to add, reorder, or remove them. The first source you return has the highest priority.

For example, this reads `service.toml` with a priority between environment variables and dotenv files:

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

File sources like this one are opt-in. Setting `toml_file` or `json_file` in the model config isn't enough on its own, and fastenv warns you if the source is missing.

| Source | Configuration |
| --- | --- |
| `JsonConfigSettingsSource` | `json_file`, `json_file_encoding` |
| `TomlConfigSettingsSource` | `toml_file`, `toml_table_header` |
| `PyprojectTomlConfigSettingsSource` | `pyproject_toml_depth`, `pyproject_toml_table_header` |
| `SecretsSettingsSource` | `secrets_dir`, environment prefix and case settings |
| `NestedSecretsSettingsSource` | Secret directories, nested separators or subdirectories, prefix, case, size and missing-directory policies |

JSON and TOML are parsed with Python's standard library. YAML is [intentionally unsupported](comparisons.md#differences-from-pydantic-settings). The pyproject source reads `[tool.pydantic-settings]` by default, so projects coming from pydantic-settings keep working. Set `pyproject_toml_table_header=("tool", "fastenv")` to use `[tool.fastenv]` instead.

Do you keep dotenv files in S3-compatible object storage? Download the file with fastenv's [object storage client](cloud-object-storage.md#downloading-files), then pass its path to `await Settings.load(_env_file=...)`.

#### Writing your own source

A source can be as simple as a function that returns a dictionary. With `await Settings.load()`, it can be an async function too:

```py
from typing import Any

from fastenv import BaseSettings


async def fetch_remote_settings() -> dict[str, Any]:
    return {"port": 9000}  # imagine an HTTP request here


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
        return (init_settings, env_settings, fetch_remote_settings)
```

An async source needs `await Settings.load()`. Calling `Settings()` with one raises `SettingsError`.

For more control, subclass `PydanticBaseSettingsSource` and implement `get_field_value` and `__call__`. If the source has I/O to await, implement `async def load(self)` as well. Otherwise, `load()` calls `__call__` for you. Sources run in priority order, and while one runs, its `current_state` holds the values merged from the sources before it and its `settings_sources_data` holds what each of them returned.

The built-in file sources read their files when they're called or loaded, never when they're constructed, so you can create them anywhere. Sources that read files or use the network should do the same.

### Application command-line arguments

fastenv doesn't generate command-line interfaces from settings models. The [comparison with pydantic-settings](comparisons.md#command-line-interfaces) explains why. Parse arguments with Click or Python's standard library `argparse` as usual, then pass the ones the user supplied to `Settings(...)`:

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

`argparse.SUPPRESS` leaves omitted options out of the mapping, so environment variables, files, and model defaults can still supply them. With Click, likewise pass only the options the user set.

Arguments passed this way have the highest priority. If you'd like them lower, return the mapping from a [custom source](#writing-your-own-source) instead.

### Coming from pydantic-settings

Already using pydantic-settings? Change `from pydantic_settings import ...` to `from fastenv import ...`, and keep importing everything else from `pydantic`. fastenv follows the public API of **pydantic-settings 2.15.0** for environment variables, local files, secret directories, and custom sources.

A few things are different on purpose:

- Dotenv files are read with [fastenv's parser](#dotenv-parsing) instead of python-dotenv.
- There are no CLI, YAML, or cloud secret service sources.
- Private methods, internal module paths, and exact error messages may not match.

The [comparison with pydantic-settings](comparisons.md#differences-from-pydantic-settings) covers each difference in detail.

fastenv's settings code is an original implementation, written from the public documentation and signatures. No pydantic-settings code or tests were copied. The [test suite](contributing.md#testing-with-pytest) checks validation, source priority, aliases, nested values, and file loading without pydantic-settings or python-dotenv installed. It can't cover every Pydantic type and option, so try out the settings you rely on when you migrate.

For more background, see [fastenv discussion 21](https://github.com/br3ndonland/fastenv/discussions/21), [pydantic-settings](https://github.com/pydantic/pydantic-settings), and the [Pydantic settings documentation](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/).

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
