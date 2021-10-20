# Comparisons

## environ

The [Python standard library `os` module](https://docs.python.org/3/library/os.html) offers operating system utilities, including `os.environ` for working with environment variables. `os.environ` only handles strings, and doesn't include tools for file I/O.

`os.environ` is instantiated from `os._Environ`, which is an implementation of [`collections.abc.MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping). The source code for `os.environ` can be found in _[python/cpython/Lib/os.py](https://github.com/python/cpython/blob/0a7dcbdb13f1f2ab6e76e1cff47e80fb263f5da0/Lib/os.py#L663-L778)_, and the source code for `collections.abc.MutableMapping` can be found in _[python/cpython/Lib/\_collections_abc.py](https://github.com/python/cpython/blob/0a7dcbdb13f1f2ab6e76e1cff47e80fb263f5da0/Lib/_collections_abc.py#L875-L959)_. As explained in the docstring for `MutableMapping`:

> A MutableMapping is a generic container for associating key/value pairs.
>
> This class provides concrete generic implementations of all methods except for `__getitem__`, `__setitem__`, `__delitem__`, `__iter__`, and `__len__`.

Subclasses of `collections.abc.MutableMapping`, such as `os._Environ`, need to provide implementations of each of those methods.

[Type stubs](https://mypy.readthedocs.io/en/stable/stubs.html) for `os.environ` are in _[python/typeshed/stdlib/os/\_\_init\_\_.pyi](https://github.com/python/typeshed/blob/14add7520bb2f6dd468338c50fe94a5ac9a6ae0c/stdlib/os/__init__.pyi#L186-L223)_. Stubs for `collections.abc.MutableMapping` are in _[python/typeshed/stdlib/typing.pyi](https://github.com/python/typeshed/blob/14add7520bb2f6dd468338c50fe94a5ac9a6ae0c/stdlib/typing.pyi#L453-L480)_ (these are the type stubs for the standard library `typing` module, which [aliases `collections.abc.MutableMapping`](https://github.com/python/cpython/blob/0a7dcbdb13f1f2ab6e76e1cff47e80fb263f5da0/Lib/typing.py#L1670)).

See the [`os` module docs](https://docs.python.org/3/library/os.html) and the [docs on mapping types](https://docs.python.org/3/library/stdtypes.html#mapping-types-dict) for more information.

## environs

-   [environs](https://github.com/sloria/environs) is a project with useful features for managing _.env_ files and application settings. Its API was inspired by [django-environ](https://github.com/joke2k/django-environ) and [envparse](https://github.com/rconradharris/envparse) (and the maintainers [considered](https://github.com/rconradharris/envparse/issues/12) merging environs and envparse into one project). The _README_ [compares](https://github.com/sloria/environs#why) environs to `os.environ`, and justifies the additional features that environs provides.
-   While it _separates_ config from code, as suggested by the [twelve-factor app](https://12factor.net/config) methodology, it also _combines_ environment variables and settings. Environment variables and their type-casted setting counterparts are combined into the same model.
-   Initially, the source code wasn't consistently type-annotated ([sloria/environs#186](https://github.com/sloria/environs/issues/186)), but based on its [PEP 561](https://www.python.org/dev/peps/pep-0561/) marker file, it appears to be type-annotated now.
-   Depends on python-dotenv ([sloria/environs#196](https://github.com/sloria/environs/issues/196)), so it inherits the limitations described in the [python-dotenv section](#python-dotenv).

## _pydantic_

### Settings configuration

_pydantic_ offers a [`BaseSettings` model](https://pydantic-docs.helpmanual.io/usage/settings/). Settings class attributes are automatically read from environment variables, and the full power of _pydantic_ data parsing/validation can be applied.

<!-- prettier-ignore -->
!!!example "Simple _pydantic_ settings model"

    ```py
    import os

    from pydantic import BaseSettings

    os.environ["BOOLEAN_SETTING"] = "false"
    os.environ["INTEGER_SETTING"] = "123"
    os.environ["STRING_SETTING"] = "example_value"


    class SimpleSettings(BaseSettings):
        boolean_setting: bool = True
        integer_setting: int = 000
        string_setting: str = "default_value"


    print(SimpleSettings().dict())
    # {"boolean_setting": False, "integer_setting": 123, "string_setting": "example_value"}
    ```

### File I/O

-   In addition to reading environment variables that have already been set, _pydantic_ can load environment variables from _.env_ files. However, it depends on python-dotenv to load _.env_ files, so it inherits the limitations described in the [python-dotenv section](#python-dotenv).
-   If no _.env_ file is found at the path provided, _pydantic_ will fail silently, rather than raising a `FileNotFoundError`. This can lead to issues if applications depend on environment variables that _pydantic_ fails to load.

## python-decouple

-   [python-decouple](https://github.com/henriquebastos/python-decouple) loads settings from _.env_ and _.ini_ files. Its supported configuration file format appears to be inspired by [Foreman](https://github.com/ddollar/foreman), a Ruby configuration management tool.
-   Variables are set with calls to instances of its `AutoConfig` class, which offers type-casting to convert strings to other Python types: `config("DEBUG", cast=bool)`.
-   Source code is not type-annotated.
-   Classes inherit from `object`, and therefore require their own implementations of methods already present in other data structures. This could be easily eliminated by inheriting from a mapping data structure such as `collections.abc.MutableMapping`.
-   Continues supporting Python 2 after its [end-of-life](https://www.python.org/doc/sunset-python-2/), and has not been tested on the latest versions of Python 3.

## python-dotenv

[python-dotenv](https://github.com/theskumar/python-dotenv) is a package for loading _.env_ files and setting environment variables. It was [started](https://github.com/theskumar/python-dotenv/commit/5fc02b7303e8854243970e12564f2433da7a1f7f) by Django co-creator Jacob Kaplan-Moss in 2013, and was originally called django-dotenv. It is used by [Uvicorn](https://www.uvicorn.org/) and _[pydantic](https://pydantic-docs.helpmanual.io/usage/settings/)_, and suggested in the [FastAPI docs](https://fastapi.tiangolo.com/advanced/settings/).

### Environment variables

-   Its primary data structure, `dotenv.main.DotEnv`, inherits from `object`. As a result, it requires its own mapping methods (such as `dict()`) that could be obviated by inheriting from a mapping data structure such as `collections.abc.MutableMapping`.
-   Other methods have confusing, counter-intuitive APIs. For example, the `load_dotenv()` function is supposed to "Parse a .env file and then load all the variables found as environment variables," according to its docstring. However, the function always returns `True`, even if no _.env_ file is found or no environment variables are set, because of `DotEnv.set_as_environment_variables()`. Furthermore, this confusing behavior is not documented, because, as the maintainer [commented](https://github.com/theskumar/python-dotenv/issues/164#issuecomment-494750043), "The return value of `load_dotenv` is undocumented as I was planning to do something useful with it, but could not settle down to one."

### File I/O

-   Loads files with the synchronous `open()` built-in function. Async support is not provided.
-   Does not integrate with object storage like AWS S3.

### Project maintenance

-   Continued supporting Python 2 after its [end-of-life](https://www.python.org/doc/sunset-python-2/) (until 0.19.0), so it had to use [Python 2 type comments](https://mypy.readthedocs.io/en/stable/python2.html) and other legacy cruft.
-   Maintainers have not been receptive to improvements (see [theskumar/python-dotenv#263](https://github.com/theskumar/python-dotenv/pull/263) for context).

### Comparing fastenv and python-dotenv

#### `DotEnv`

-   Both fastenv and python-dotenv provide a `DotEnv` class for managing environment variables
-   `fastenv.DotEnv` inherits from `collections.abc.MutableMapping`, `dotenv.main.DotEnv` inherits from `object`
-   fastenv includes `DotEnv` in its `__all__`, python-dotenv does not (it must be directly imported from `dotenv.main`)

#### `find_dotenv`

-   fastenv: `await fastenv.find_dotenv()` (async)
-   python-dotenv: `dotenv.find_dotenv()` (sync)
-   Both fastenv and python-dotenv look for `".env"` by default
-   Both python-dotenv and fastenv return `os.PathLike` objects
-   fastenv raises `FileNotFoundError` exceptions by default if files are not found, python-dotenv does not

#### `load_dotenv`

-   fastenv: `await fastenv.load_dotenv()` (async)
-   python-dotenv: `dotenv.load_dotenv()` (sync)
-   `fastenv.load_dotenv` can load multiple _.env_ files in a single call, `dotenv.load_dotenv` cannot
-   `fastenv.load_dotenv` logs the number of environment variables loaded, `dotenv.load_dotenv` does not
-   `fastenv.load_dotenv` returns a `DotEnv` model, `dotenv.load_dotenv` returns `True` (even if no _.env_ file was found and no environment variables were loaded)

#### `find_dotenv` with `load_dotenv`

Users who would like to ensure their _.env_ files are found, and log the result, should be aware that `dotenv.load_dotenv`:

-   Only calls `find_dotenv` if a file path is not provided, and does not pass an argument through to `find_dotenv` to raise exceptions if the file is not found
-   Requires a call to `DotEnv.set_as_environment_variables` to actually set environment variables
-   Does not provide logging
-   Does not provide exception handling (its `verbose` argument does not necessarily raise an exception)
-   Does not return the `DotEnv` instance created by `load_dotenv`, but always returns `True`, even if no _.env_ file is found or no environment variables are set

Something like the following is therefore needed instead of using `dotenv.load_dotenv`:

!!!example "Finding and loading a _.env_ file with python-dotenv"

    ```py
    import logging

    from dotenv import find_dotenv
    from dotenv.main import DotEnv


    def find_and_load_my_dotenv(env_file: str = ".env") -> DotEnv:
        try:
            logger = logging.getLogger()
            source = find_dotenv(filename=env_file, raise_error_if_not_found=True)
            dotenv = DotEnv(source, verbose=True)
            dotenv.set_as_environment_variables()
            logger.info(
              f"Python-dotenv loaded {len(dotenv.dict())} variables from {env_file}"
            )
            return dotenv
        except Exception as e:
            logger.error(f"Error loading {env_file}: {e.__class__.__qualname__} {e}")
            raise
    ```

The above effect can be accomplished with fastenv in a single call, `await fastenv.load_dotenv(find_source=True)`. This call to `fastenv.load_dotenv`:

-   Finds the _.env_ file (`find_source=True`) with its `find_dotenv` method and the file name provided (`".env"` by default), logging and raising a `FileNotFoundError` if not found
-   Sets environment variables automatically
-   Logs successes and errors automatically
-   Raises exceptions by default
-   Returns a `DotEnv` instance

#### `dotenv_values`

-   fastenv: `await fastenv.dotenv_values()` (async)
-   python-dotenv: `dotenv.dotenv_values()` (sync)
-   `fastenv.dotenv_values` offers a `find_dotenv` argument to find files before loading and returning values, `dotenv.dotenv_values` does not
-   `fastenv.dotenv_values` offers a `raise_exceptions` argument to determine whether or not exceptions will be raised, `dotenv.dotenv_values` does not (its `verbose` argument does not necessarily raise an exception)
-   `fastenv.dotenv_values` logs successes and errors automatically, `dotenv.dotenv_values` does not

#### Writing to _.env_ files

-   fastenv: `await fastenv.dump_dotenv()` (async, and writes an entire `DotEnv` model to a file)
-   python-dotenv: `dotenv.get_key()`, `dotenv.set_key()`, `dotenv.unset_key()` (sync, and can only write single variables to a file)

## Starlette

### Settings configuration

Starlette offers a [config module](https://www.starlette.io/config/) for working with environment variables and settings, which takes inspiration from [python-decouple](https://github.com/henriquebastos/python-decouple). Settings are created by calling a Starlette `Config` instance. Constant notation is suggested for settings (`UPPERCASE_WITH_UNDERSCORES`).

<!-- prettier-ignore -->
!!!example

    ```py
    import starlette.config

    config = starlette.config.Config()
    FOO_CONSTANT = config("FOO_VARIABLE", cast=str, default="baz")
    ```

Starlette will look for an environment variable `FOO_VARIABLE`. For example, setting `FOO_VARIABLE=bar` in the environment will result in `FOO_CONSTANT = "bar"`. If the environment variable is unset, the result will be `FOO_CONSTANT = "baz"`. The `cast` keyword argument allows use of Starlette type-casting.

### Type-casting

Type-casting provides improvements over some aspects of the standard library. For example, Starlette intuitively casts Boolean values, unlike the Python built-in `bool` type:

<!-- prettier-ignore -->
!!!example "Type-casting with `starlette.config`"

    ```py
    .venv ❯ python3

    >>> bool("false")
    True
    >>> import starlette.config
    >>> config = starlette.config.Config()
    >>> config("BOOLEAN_SETTING", cast=bool, default="false")
    False
    ```

### One-way configuration preference

Starlette has an opinionated one-way configuration preference (environment variables -> Starlette `Config` instance). To avoid modifying environment variables after they have been loaded into a Starlette `Config` instance, [Starlette provides its own mapping onto `os.environ`](https://www.starlette.io/config/#reading-or-modifying-the-environment) (`starlette.config.environ`), which will raise an exception on attempts to change an environment variable that has already been loaded into a corresponding setting on a `Config` instance.

While it is useful to have `starlette.config.environ` synchronized with `os.environ`, the downside is that `starlette.config.environ` contains local environment variables loaded from `os.environ`, and therefore wouldn't typically be dumped to a file.

It is also important to note that the one-way preference will only be enforced when using `starlette.environ`. If a variable is changed using `os.environ`, it will be updated correspondingly in `starlette.environ`, but no exception will be raised, and the `Config` instance value will not be updated.

<!-- prettier-ignore -->
!!!example "Environment variables with `starlette.config`"

    ```py
    .venv ❯ python3

    >>> import os
    >>> import starlette.config
    >>> os.environ.get("FOO_VARIABLE")
    >>> starlette.config.environ["FOO_VARIABLE"] = "bar"
    >>> os.environ.get("FOO_VARIABLE")
    'bar'
    >>> config = starlette.config.Config()
    >>> FOO_CONSTANT = config("FOO_VARIABLE", cast=str, default="baz")
    >>> FOO_CONSTANT
    'bar'
    >>> starlette.config.environ["FOO_VARIABLE"] = "foo"
    Traceback (most recent call last):
    File ".venv/lib/python3.9/site-packages/starlette/config.py", line 26, in __setitem__
        raise EnvironError(
    starlette.config.EnvironError: Attempting to set environ['FOO_VARIABLE'],
    but the value has already been read.
    >>> os.environ["FOO_VARIABLE"] = "foo"
    >>> os.environ["FOO_VARIABLE"]
    'foo'
    >>> starlette.config.environ["FOO_VARIABLE"]
    'foo'
    >>> FOO_CONSTANT
    'bar'
    ```

### File I/O

-   Starlette `Config` accepts an `env_file` keyword argument, which should point to a _.env_ file on disk. It loads the file with the synchronous `open()` built-in function.
-   If no _.env_ file is found at the path provided by `Config(env_file)`, Starlette will fail silently, rather than raising a `FileNotFoundError`. This can lead to issues if applications depend on environment variables that Starlette fails to load.
-   Starlette `Config` does not support multiple _.env_ files ([encode/starlette#432](https://github.com/encode/starlette/issues/432)).

### The future of `starlette.config`

From [encode/starlette#432](https://github.com/encode/starlette/issues/432#issuecomment-471617467):

> I guess we may actually end up pulling the configuration stuff out into a strictly seperate package (or indeed even just pointing at python-decouple - since it's the same style).
>
> With 12-factor config you really should have a fairly small set of environment. (Eg. the database configuration should just be a single URL.)
>
> What we _will_ want to do though is provide really good examples of how to arrange things sensibly, so that eg. you have a project that has a `settings.py` that includes a whole bunch of project configuration, and which you can arrange into seperate bits, and demonstrate clearly how the _environment_ should be a small set of variables, but the project _settings_ may be more comprehensive.
>
> We could perfectly well also point to other configuration-manangement packages that're out there as alternatives.

## Other

-   [dotenvy](https://github.com/chickenzord/dotenvy) can load _.env_ files and apply a type schema to the variables. It does not appear to be actively maintained.
-   [env](https://github.com/MasterOdin/env) does not add much beyond `os.environ` (does not even load files), has not been released since 2012, and does not appear to be actively maintained.
-   [envparse](https://github.com/rconradharris/envparse) offers features for parsing and type-casting environment variables, but does not appear to be actively maintained.
-   [python-configurator](https://github.com/guitarpoet/python-configurator) depends on python-dotenv and appears to emphasize TOML settings files.
