# ⚙️ fastenv 🚀

_Unified environment variable and settings management for FastAPI and beyond_

[![PyPI](https://img.shields.io/pypi/v/fastenv?color=success)](https://pypi.org/project/fastenv/) [![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen?logo=pytest&logoColor=white)](https://coverage.readthedocs.io/en/latest/) [![ci](https://github.com/br3ndonland/fastenv/workflows/ci/badge.svg)](https://github.com/br3ndonland/fastenv/actions/workflows/ci.yml) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Description

fastenv [\[fæst iː ən v\]](https://en.wikipedia.org/wiki/Help:IPA/English) is a Python package for managing environment variables and application settings.

[Environment variables](https://en.wikipedia.org/wiki/Environment_variable) are key-value pairs provided to the operating system with syntax like `VARIABLE_NAME=value`. Collections of environment variables are stored in files commonly named _.env_ and called "dotenv" files. The Python standard library `os` module provides tools for reading environment variables, such as `os.getenv("VARIABLE_NAME")`, but only handles strings, and doesn't include tools for file I/O. Additional logic is therefore needed to load environment variables from files before they can be read by Python, and to convert variables from strings to other Python types.

This project aims to:

- [x] **Replace the aging [python-dotenv](https://github.com/theskumar/python-dotenv) project** with a similar, but more intuitive API, and modern syntax and tooling.
- [x] **Implement asynchronous file I/O**. Reading and writing files can be done asynchronously with packages like [AnyIO](https://github.com/agronholm/anyio).
- [x] **Implement asynchronous object storage integration**. Dotenv files are commonly kept in cloud object storage, but environment variable management packages typically don't integrate with object storage clients. Additional logic is therefore required to download _.env_ files from object storage prior to loading environment variables. This project aims to integrate with S3-compatible object storage, with a focus on downloading and uploading file objects.
- [x] **Read settings from TOML**. [It's all about _pyproject.toml_ now](https://snarky.ca/what-the-heck-is-pyproject-toml/). The Python community has pushed [PEP 517](https://www.python.org/dev/peps/pep-0517/) build tooling and [PEP 518](https://www.python.org/dev/peps/pep-0518/) build requirements forward, and [even `setuptools` has come around](https://setuptools.readthedocs.io/en/latest/build_meta.html). [PEP 621](https://www.python.org/dev/peps/pep-0621/) defined how to store package metadata and dependencies in _pyproject.toml_. The [Starlette integration](settings.md#toml-settings) makes this metadata available as application settings.
- [x] **Unify settings management for FastAPI**. [Pydantic](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/) and [Starlette](https://www.starlette.io/config/) provide different APIs for loading environment variables and configuring application settings. When [configuring a FastAPI application](https://fastapi.tiangolo.com/advanced/settings/), the [Pydantic integration](settings.md#pydantic-integration) and [Starlette integration](settings.md#starlette-integration) provide these settings APIs backed by a shared fastenv dotenv parser.

The source code is 100% type-annotated and unit-tested.

For additional background on the project, see [www.bws.bio/projects/fastenv](https://www.bws.bio/projects/fastenv).

## Quickstart

Install fastenv into a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install fastenv
```

Then start a REPL session and try it out:

```sh
.venv ❯ python
```

```py
# instantiate a DotEnv with a variable
import fastenv

dotenv = fastenv.DotEnv("EXAMPLE_VARIABLE=example_value")
# add a variable with dictionary syntax
dotenv["ANOTHER_VARIABLE"] = "another_value"
# delete a variable
del dotenv["ANOTHER_VARIABLE"]
# add a variable by calling the instance
dotenv("I_THINK_FASTENV_IS=awesome")
# {'I_THINK_FASTENV_IS': 'awesome'}
# return a dict of the variables in the DotEnv instance
dict(dotenv)
# {'EXAMPLE_VARIABLE': 'example_value', 'I_THINK_FASTENV_IS': 'awesome'}
# save the DotEnv instance to a file
import anyio

anyio.run(fastenv.dump_dotenv, dotenv)
# Path('/path/to/this/dir/.env')
```

Use fastenv in your FastAPI app:

```py
from contextlib import asynccontextmanager
from typing import AsyncGenerator, TypedDict

import fastenv
from fastapi import FastAPI, Request


class LifespanState(TypedDict):
    settings: fastenv.DotEnv


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[LifespanState]:
    """Configure app lifespan.

    https://fastapi.tiangolo.com/advanced/events/
    https://www.starlette.io/lifespan/
    """
    settings = await fastenv.load_dotenv(".env")
    lifespan_state: LifespanState = {"settings": settings}
    yield lifespan_state


app = FastAPI(lifespan=lifespan)


@app.get("/settings")
async def get_settings(request: Request) -> dict[str, str]:
    settings = request.state.settings
    return dict(settings)
```

## Documentation

For typed application settings, use [`fastenv.settings.BaseSettings`](settings.md#pydantic-integration) with `fastenv[settings]`, or [`fastenv.StarletteConfig`](settings.md#starlette-integration) with `fastenv[starlette]`. Both integrations combine settings sources using fastenv dotenv parsing without depending on python-dotenv.

Documentation is built with [Zensical](https://zensical.org/), deployed to [Vercel](https://vercel.com/) using the [Vercel project configuration](https://vercel.com/docs/project-configuration) in `vercel.json`, and available at [fastenv.bws.bio](https://fastenv.bws.bio) and [fastenv.vercel.app](https://fastenv.vercel.app).
