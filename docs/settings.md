---
icon: lucide/settings
---

# Application settings

## Starlette integration

`fastenv.StarletteConfig` extends [Starlette's `Config`](https://www.starlette.io/config/) with multiple dotenv files, TOML settings, and configurable file error handling. It inherits Starlette's settings lookup, type casting, defaults, and environment prefixes.

Install the optional integration into your project's virtual environment:

```sh
uv pip install 'fastenv[starlette]'
```

Create a `.env` file:

```sh
DEBUG=false
PORT=8000
ALLOWED_HOSTS=localhost,127.0.0.1
```

Read settings with the same calling convention as Starlette:

```py
import fastenv
from starlette.datastructures import CommaSeparatedStrings

config = fastenv.StarletteConfig(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
PORT = config("PORT", cast=int, default=8000)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=CommaSeparatedStrings, default="localhost")
```

You can also import the same class as `Config`:

```py
from fastenv.settings.starlette_config import Config
```

Starlette is an optional dependency. Install `fastenv[starlette]` before importing this class. The rest of fastenv remains usable without Starlette installed.

## Sources and precedence

The constructor keeps Starlette's positional arguments, `env_file`, `environ`, `env_prefix`, and `encoding`, in that order. The new `toml_file`, `toml_table`, and `raise_exceptions` arguments are keyword-only.

| Argument | Default | Purpose |
| --- | --- | --- |
| `env_file` | `None` | A string or path-like object, or a list or tuple of paths to dotenv files. |
| `environ` | `starlette.config.environ` | The mapping used to read environment variables. |
| `env_prefix` | `""` | A prefix added to setting names before looking up values. |
| `encoding` | `"utf-8"` | The encoding used to read dotenv files. |
| `toml_file` | `None` | A string or path-like object pointing to a TOML file, read as UTF-8. |
| `toml_table` | `"project"` | The top-level TOML table to load. |
| `raise_exceptions` | `True` | Whether file loading errors are raised after being logged. |

No files are loaded unless their paths are provided. Relative paths are resolved from the current working directory.

Values are looked up in this order, from highest to lowest priority:

1. The environment mapping.
2. Dotenv files, with later files overriding earlier files.
3. The selected TOML table.
4. The `default` passed to the setting lookup.

For example, this configuration loads base values from `pyproject.toml`, overrides them with `.env`, then overrides those values with `.env.local`. An existing environment variable overrides all three files.

```py
import fastenv

config = fastenv.StarletteConfig(
    env_file=[".env", ".env.local"],
    toml_file="pyproject.toml",
)
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
import fastenv

config = fastenv.StarletteConfig(toml_file="pyproject.toml")

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

## File errors and application startup

Missing, unreadable, or invalid input files are logged and raise an exception by default. To allow optional files, pass `raise_exceptions=False`. A failed source is skipped, while successfully loaded sources remain available:

```py
import fastenv

config = fastenv.StarletteConfig(
    env_file=[".env", ".env.local"],
    toml_file="pyproject.toml",
    raise_exceptions=False,
)
DEBUG = config("DEBUG", cast=bool, default=False)
```

This option only controls source loading errors. Missing required settings and invalid casts still raise exceptions when settings are read.

Construction reads files synchronously and works inside an already running event loop. Create the config once during application startup to avoid reading files on each request. For asynchronous dotenv loading that sets environment variables, use [`fastenv.load_dotenv`](dotenv.md#loading-a-env-file).
