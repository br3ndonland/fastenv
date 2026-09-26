---
icon: lucide/settings
---

# Application settings

## Pydantic integration

`fastenv.settings` provides Pydantic settings models using fastenv to parse dotenv files. It is an original implementation based on the public pydantic-settings 2.15.0 API, with [intentional differences](comparisons.md#differences-from-pydantic-settings). Neither pydantic-settings nor python-dotenv is a runtime dependency.

Install the optional integration into your project's virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'fastenv[settings]'
```

Change settings imports to `fastenv.settings`. Continue importing models, fields, aliases, validators, and types from `pydantic`:

```py
from pydantic import BaseModel

from fastenv.settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
```

For example, `SERVICE_DEBUG=true` becomes a boolean. `SERVICE_DATABASE__PORT=6543` overrides the nested port. A JSON object in `SERVICE_DATABASE` can supply several nested values, and individual nested variables override its matching members.

### Sources and priority

The default order, from highest to lowest priority, is:

1. Command-line arguments, when enabled.
2. Constructor arguments.
3. Process environment variables.
4. Dotenv files, with later files overriding earlier files.
5. Secret files, with later directories overriding earlier directories.
6. Model defaults.

Mappings from different sources are merged recursively. Pydantic validates the merged input and applies field defaults. Default values are validated too. Unknown environment variables are ignored. Unknown constructor and dotenv values are rejected unless `extra="ignore"` or `extra="allow"` is configured.

Per-instance options use the same leading underscore as pydantic-settings. For example, `Settings(_env_file="production.env")` selects another file, and `Settings(_env_file=None)` disables dotenv loading. `Settings(_env_prefix="OTHER_")` changes the prefix for that instance.

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

`parse_dotenv` is also available without Pydantic:

```py
import fastenv

values = fastenv.parse_dotenv("PORT=8000 LABEL='local service'")
assert values == {"PORT": "8000", "LABEL": "local service"}
```

`DotEnv`, `load_dotenv`, and `dotenv_values` retain their existing environment mutation behavior. The settings constructor is synchronous, like Pydantic's model constructor. It can be called inside an event loop without starting another loop. To avoid blocking the loop during file I/O, use a worker thread:

```py
import anyio

settings = await anyio.to_thread.run_sync(Settings)
```

### Custom and file sources

Override `settings_customise_sources` to add, reorder, or remove sources. The first returned source has the highest priority. A source can be a callable returning a dictionary, or a subclass of `PydanticBaseSettingsSource` with `get_field_value` and `__call__` implementations. Source instances expose `current_state` and `settings_sources_data` while they are being evaluated.

```py
from fastenv.settings import BaseSettings, TomlConfigSettingsSource


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

For dotenv files stored in S3-compatible object storage, use fastenv's [asynchronous object storage client](cloud-object-storage.md#downloading-files) to download a file before loading its path with `Settings(_env_file=...)`. The client is available through `fastenv[cloud]` and does not depend on Boto3. Built-in cloud secret services are outside this integration's scope. See the [comparison with pydantic-settings](comparisons.md#differences-from-pydantic-settings).

### Command-line settings

Enable argument parsing explicitly:

```py
from fastenv.settings import BaseSettings, SettingsConfigDict


class Options(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True, cli_implicit_flags=True)
    port: int = 8000
    verbose: bool = False


options = Options()
```

This accepts options such as `--port 9000 --verbose`. A list supplied with `_cli_parse_args=["--port", "9000"]` avoids reading process arguments.

The CLI includes nested options, JSON values, repeated and comma-separated collections, aliases, enum values, boolean flags, positional arguments, subcommands, unknown argument capture, and help configuration. `CliApp` runs model commands, including async commands, and can serialize models back to argument lists. `CliSettingsSource` supports integration with an existing parser.

Public CLI exports include `CLI_SUPPRESS`, `CliApp`, `CliSettingsSource`, `CliSubCommand`, `CliPositionalArg`, `CliImplicitFlag`, `CliExplicitFlag`, `CliDualFlag`, `CliToggleFlag`, `CliSuppress`, `CliUnknownArgs`, `CliMutuallyExclusiveGroup`, and `get_subcommand`.

### Compatibility and verification

The compatibility target is the released **pydantic-settings 2.15.0** public API for environment, local file, custom source, and CLI settings, imported through `fastenv.settings`. YAML, cloud providers, and parser differences are documented in the [comparison with pydantic-settings](comparisons.md#differences-from-pydantic-settings). Internal module paths, private methods, exact error text, and exact CLI help formatting are not compatibility contracts. The fastenv package version remains available as `fastenv.settings.__version__`.

The implementation was written from public documentation, signatures, and independently authored behavioral probes. No pydantic-settings implementation or tests were copied. The reference package is used only for development. From the repository root, install the local settings integration and pinned reference package in a separate virtual environment, then run the compatibility checks:

```sh
python3 -m venv .venv-compat
. .venv-compat/bin/activate
python -m pip install -e '.[settings]' 'pydantic-settings==2.15.0'
python -m scripts.check_settings_compatibility
deactivate
```

This checks supported public exports, verifies the intentional YAML and cloud API omissions, and compares settings behavior across both implementations. The regular test suite covers the integration without installing pydantic-settings or python-dotenv. These checks exercise a defined set of behaviors and are not proof of exhaustive equivalence for all Pydantic types or third-party parser implementations.

Background: [fastenv discussion 21](https://github.com/br3ndonland/fastenv/discussions/21), [pydantic-settings](https://github.com/pydantic/pydantic-settings), and the [Pydantic settings documentation](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/).

## Starlette integration

`fastenv.StarletteConfig` extends [Starlette's `Config`](https://starlette.dev/config/) with asynchronous loading of multiple dotenv files and TOML settings, plus configurable file error handling. It inherits Starlette's settings lookup, type casting, defaults, and environment prefixes.

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

### Sources and precedence

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

### TOML settings

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

### Starlette behavior

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

### File errors

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

### Application startup

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
