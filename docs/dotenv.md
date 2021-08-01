# Dotenv files

## Overview

Collections of environment variables are stored in files commonly named _.env_ and called "dotenv" files. The fastenv package provides methods for reading and writing these files.

## Getting started

To get started, let's set up a virtual environment and install fastenv from the command line. If you've been through the [environment variable docs](environment.md#getting-started), you're all set.

!!!example "Setting up a virtual environment"

    ```sh
    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install fastenv
    ```

We'll work with an example _.env_ file that contains variables in various formats. Copy the code block below using the "Copy to clipboard" icon in the top right of the code block, paste the contents into a new file in your text editor, and save it as `.env`.

!!!example "Example .env file"

    ```sh
    # .env
    AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE
    CSV_VARIABLE=comma,separated,value
    EMPTY_VARIABLE=''
    # comment
    INLINE_COMMENT=no_comment  # inline comment
    JSON_EXAMPLE='{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}'
    PASSWORD='64w2Q$!&,,[EXAMPLE'
    QUOTES_AND_WHITESPACE='text and spaces'
    URI_TO_DIRECTORY='~/dev'
    URI_TO_S3_BUCKET=s3://mybucket/.env
    URI_TO_SQLITE_DB=sqlite:////path/to/db.sqlite
    URL_EXAMPLE=https://start.duckduckgo.com/

    ```

These environment variables are formatted as described in the [environment variable docs](environment.md#tips).

## Loading a _.env_ file

Files can be loaded with `await fastenv.load_dotenv()`. File I/O is implemented with [AnyIO](https://anyio.readthedocs.io/en/stable/fileio.html), and the function returns a [`DotEnv`](environment.md) instance.

!!!info "Asynchronous functions"

    You'll see some functions in this section defined with `async def`.

    Standard Python functions defined with `def` are synchronous. Synchronous Python programs execute one step at a time. Python's [global interpreter lock](https://docs.python.org/3/glossary.html#term-global-interpreter-lock) (GIL) blocks the next steps until the current step is done.

    When functions are defined with `async def` instead of `def`, they become [coroutines](https://docs.python.org/3/library/asyncio-task.html). These coroutines can run asynchronously, meaning that many steps can run at the same time without blocking the others, and the Python program can `await` each coroutine. Asynchronous coroutines require special consideration in Python. For example, in order to use `await`, the statement has to be inside of an `async def` coroutine, and a method like `asyncio.run()` has to be used to run the program.

    See the Python standard library [`asyncio`](https://docs.python.org/3/library/asyncio-api-index.html) docs for more details, and the [FastAPI docs](https://fastapi.tiangolo.com/async/) for some additional explanation and context.

    The fastenv package uses [AnyIO](https://anyio.readthedocs.io/en/stable/index.html) for its asynchronous functions. AnyIO uses similar syntax to `asyncio`, such as `anyio.run()` instead of `asyncio.run()`, but offers many additional features.

    If you're working with async-enabled web server tools like [Uvicorn](https://www.uvicorn.org/), [Starlette](https://www.starlette.io/), and [FastAPI](https://fastapi.tiangolo.com/), you don't need to include the `anyio.run()` part. It will be handled for you automatically when you start your server.

    See the [Trio docs](https://trio.readthedocs.io/en/stable/reference-io.html#asynchronous-filesystem-i-o) for an informative justification of asynchronous file I/O.

The example below demonstrates how this works. Note that this is written as a _script_, not a REPL session. Save the script as `example.py` in the same directory as the `.env` file, then run the script from within the virtual environment.

!!!example "Loading a _.env_ file into a `DotEnv` model"

    ```py
    #!/usr/bin/env python3
    # example.py
    import anyio
    import fastenv


    async def load_my_dotenv() -> fastenv.DotEnv:
        dotenv = await fastenv.load_dotenv()
        print(dotenv.source)
        print(dict(dotenv))
        return dotenv


    if __name__ == "__main__":
        anyio.run(load_my_dotenv)
    ```

    ```sh
    .venv ❯ python example.py

    # output formatted for clarity
    /Users/brendon/dev/fastenv-docs/.env
    {
      'AWS_ACCESS_KEY_ID': 'AKIAIOSFODNN7EXAMPLE',
      'AWS_SECRET_ACCESS_KEY': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE',
      'CSV_VARIABLE': 'comma,separated,value',
      'EMPTY_VARIABLE': '',
      'INLINE_COMMENT': 'no_comment',
      'JSON_EXAMPLE': '{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}',
      'PASSWORD': '64w2Q$!&,,[EXAMPLE',
      'QUOTES_AND_WHITESPACE': 'text and spaces',
      'URI_TO_DIRECTORY': '~/dev',
      'URI_TO_S3_BUCKET': 's3://mybucket/.env',
      'URI_TO_SQLITE_DB': 'sqlite:////path/to/db.sqlite',
      'URL_EXAMPLE': 'https://start.duckduckgo.com/'
    }
    ```

Comments were removed automatically, and each `KEY=value` string was converted into a `"KEY": "value"` pair in the dictionary. Each variable from the _.env_ file was set as an environment variable for the Python program to use. The `dotenv.source` attribute shows the path to the _.env_ file that was loaded.

!!!tip "Finding a _.env_ file with `fastenv.find_dotenv()`"

    If you're not sure of the exact path to the _.env_ file, fastenv can locate it for you. Adding the `find_source=True` argument (`await fastenv.load_dotenv(find_source=True)`) will instruct fastenv to look for a _.env_ file using its `find_dotenv` method. By default, it will look for a file named `.env`, starting in the current working directory and walking upwards until a file with the given file is found. It will return the path to the file if found, or raise a `FileNotFoundError` if not found.

    If you like, you may also use the `fastenv.find_dotenv` method on its own. It accepts a path to (or just the name of) the file, and the directory in which to start its search.

!!!tip "Simplifying serialization with `fastenv.dotenv_values()`"

    In some cases, you may simply want a dictionary of the keys and values in a _.env_ file, instead of the `DotEnv` model itself. Rather than running `await fastenv.load_dotenv()` and then `dict(dotenv)` to serialize the model into a dictionary, as we did in the example above, consider `await fastenv.dotenv_values()`, which will load a _.env_ file and return the dictionary directly.

## Loading multiple _.env_ files

`fastenv.load_dotenv` can load more than one _.env_ file into a single `DotEnv` model. To see this, let's add another _.env_ file named `.env.override`.

!!!example "Example _.env_ file with overrides for local development"

    ```sh
    # .env.override
    APPLICATION_ENVIRONMENT=local
    CSV_VARIABLE=comma,separated,override
    URL_EXAMPLE=https://github.com
    ```

This is a common scenario in software development. Applications will often have a _.env_ file that is used for deployments, and developers will have additional _.env_ files to override deployment configurations for local development environments.

Now, we will update our `example.py` module to load both files. The order is important here. Values are set in left-to-right insertion order, so if the same variables are present in both files, values in the second file will override values in the first.

!!!example "Loading multiple _.env_ files into a `DotEnv` model"

    ```py
    #!/usr/bin/env python3
    # example.py
    import anyio
    import fastenv


    async def load_my_dotenv() -> fastenv.DotEnv:
        dotenv = await fastenv.load_dotenv()
        print(dotenv.source)
        print(dict(dotenv))
        return dotenv


    async def load_my_dotenvs(*filenames: str) -> fastenv.DotEnv:
        dotenv = await fastenv.load_dotenv(*filenames)
        print(dotenv.source)
        print(dict(dotenv))
        return dotenv


    if __name__ == "__main__":
        # anyio.run(load_my_dotenv)
        anyio.run(load_my_dotenvs, ".env", ".env.override")
    ```

    ```sh
    .venv ❯ python example.py

    # output formatted for clarity
    [
      Path('/Users/brendon/dev/fastenv-docs/.env'),
      Path('/Users/brendon/dev/fastenv-docs/.env.override')
    ]
    {
      'AWS_ACCESS_KEY_ID': 'AKIAIOSFODNN7EXAMPLE',
      'AWS_SECRET_ACCESS_KEY': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE',
      'CSV_VARIABLE': 'comma,separated,override',
      'EMPTY_VARIABLE': '',
      'INLINE_COMMENT': 'no_comment',
      'JSON_EXAMPLE': '{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}',
      'PASSWORD': '64w2Q$!&,,[EXAMPLE',
      'QUOTES_AND_WHITESPACE': 'text and spaces',
      'URI_TO_DIRECTORY': '~/dev',
      'URI_TO_S3_BUCKET': 's3://mybucket/.env',
      'URI_TO_SQLITE_DB': 'sqlite:////path/to/db.sqlite',
      'URL_EXAMPLE': 'https://github.com',
      'APPLICATION_ENVIRONMENT': 'local'
    }
    ```

There are now two source paths listed, our variables `CSV_VARIABLE` and `URL_EXAMPLE` have been updated with the values from `.env.override`, and the new `APPLICATION_ENVIRONMENT` variable has been loaded.

## Dumping a `DotEnv` instance to a _.env_ file

We can also go in the opposite direction by using `await fastenv.dump_dotenv()` to write a `DotEnv` model out to a file. Under the hood, the `DotEnv` class uses its [`__str__()`](https://docs.python.org/3/reference/datamodel.html#object.__str__) method to deserialize the `DotEnv` instance into a string, which is then written to the file.

Let's update the `example.py` script to not only load `.env`, but also dump it back out to a different file, `.env.dump`.

!!!example "Dumping a `DotEnv` instance to a _.env_ file"

    ```py
    #!/usr/bin/env python3
    # example.py
    import anyio
    import fastenv


    async def load_my_dotenv() -> fastenv.DotEnv:
        dotenv = await fastenv.load_dotenv()
        print(dotenv.source)
        print(dict(dotenv))
        return dotenv


    async def load_my_dotenvs(*filenames: str) -> fastenv.DotEnv:
        dotenv = await fastenv.load_dotenv(*filenames)
        print(dotenv.source)
        print(dict(dotenv))
        return dotenv


    async def load_and_dump_my_dotenvs(*filenames: str) -> fastenv.DotEnv:
        dotenv = await fastenv.load_dotenv(*filenames)
        await fastenv.dump_dotenv(dotenv, ".env.dump")
        return dotenv


    if __name__ == "__main__":
        # anyio.run(load_my_dotenv)
        # anyio.run(load_my_dotenvs, ".env", ".env.override")
        anyio.run(load_and_dump_my_dotenvs, ".env", ".env.override")
    ```

Try running `python example.py` again, then opening `.env.dump` in a text editor. The new `.env.dump` file should have the variables from the `DotEnv` instance.

## Exceptions and logging

!!!tip "Handling exceptions"

    The `fastenv.load_dotenv()`, `fastenv.dotenv_values()`, and `fastenv.dump_dotenv()` methods offer a `raise_exceptions` argument to manage [exceptions](https://docs.python.org/3/library/exceptions.html).

    Python's default behavior is to raise exceptions, and fastenv follows this convention, with its default `raise_exceptions=True`. However, it may be preferable in some cases to fail silently instead of raising an exception. In these cases, `raise_exceptions=False` can be used.

    If exceptions are encountered, `fastenv.load_dotenv(raise_exceptions=False)` will return an empty `DotEnv()` instance, `fastenv.dotenv_values(raise_exceptions=False)` will return an empty dictionary, and `fastenv.dump_dotenv(raise_exceptions=False)` will simply return the path to the destination file.

!!!tip "Logging"

    fastenv will provide a small amount of [logging](https://docs.python.org/3/library/logging.html) when loading or dumping _.env_ files. Successes will be logged at the `logging.INFO` level, and errors will be logged at the `logging.ERROR` level.

    If you're managing your loggers individually in a logging configuration file, all fastenv logging uses the `"fastenv"` logger. Logging can be disabled by adding `{"loggers": {"fastenv": {"propagate": False}}}` to a logging configuration dictionary.
