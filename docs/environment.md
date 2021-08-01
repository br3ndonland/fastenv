# Environment variables

## Overview

fastenv provides a `DotEnv` class for working with environment variables.

The implementation of `fastenv.DotEnv` is based on `os.environ`, and it inherits from the same `MutableMapping` class (see [comparisons](comparisons.md) for a description of this data structure). It is intended to be a **superset of `os.environ`**, meaning that it contains some, but not all, of the variables in `os.environ`.

Practically speaking, "superset of `os.environ`" means:

-   **When an environment variable is set in an instance of `class DotEnv`, it is also set in `os.environ`**.
-   **When an environment variable is deleted from an instance of `class DotEnv`, it is also deleted from `os.environ`**.
-   **When an environment variable is set directly with `os.environ`, it is not automatically set in instances of `class DotEnv`.** `os.environ` contains variables specific to the local environment, such as `os.environ["HOME"]`, so these variables are not included in `class DotEnv` by default.

## Getting started

To get started, let's set up a virtual environment and install fastenv from the command line.

!!!example "Setting up a virtual environment"

    ```sh
    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install fastenv
    ```

Next, we will [use the Python interpreter](https://docs.python.org/3/tutorial/interpreter.html) to run a [REPL](https://en.wikipedia.org/wiki/Read%E2%80%93eval%E2%80%93print_loop) ("Read-Eval-Print Loop"), import fastenv, and create a `DotEnv` instance.

!!!example "Instantiating `fastenv.DotEnv`"

    ```py
    .venv ❯ python

    >>> import fastenv
    >>> dotenv = fastenv.DotEnv()
    ```

That's it! We are ready to start managing our environment variables with fastenv.

## Getting, setting, and deleting environment variables

### Using the `os.environ`-style API

After instantiating `class DotEnv`, environment variables can be managed in the same fashion as with `os.environ`, substituting the name of the `DotEnv` instance for `os.environ`.

Here is an example REPL session demonstrating how to use the `os.environ`-style API to manage environment variables. The `fastenv` package should be installed in the environment from which the REPL session is started.

!!!example "Using the `os.environ`-style API"

    ```py
    .venv ❯ python

    >>> import os
    >>> import fastenv
    >>> dotenv = fastenv.DotEnv()
    >>> dotenv["EXAMPLE_VARIABLE"] = "example_value"
    >>> dotenv["EXAMPLE_VARIABLE"]
    'example_value'
    >>> os.environ["EXAMPLE_VARIABLE"]
    'example_value'
    >>> del dotenv["EXAMPLE_VARIABLE"]
    >>> dotenv.getenv("EXAMPLE_VARIABLE", "variable_was_deleted")
    'variable_was_deleted'
    >>> os.getenv("EXAMPLE_VARIABLE", "variable_was_deleted")
    'variable_was_deleted'
    ```

### Instantiating `class DotEnv`

Environment variables can be set when creating instances of `class DotEnv`. Positional arguments ("args"), keyword arguments ("kwargs"), or a combination of each can be used. Positional arguments can be formatted as individual strings (`"KEY1=value1", "KEY2=value2"`), or with multiple variables in the same string separated by spaces (`"KEY1=value1 KEY2=value2"`).

!!!example "Instantiating `class DotEnv` with variables"

    ```py
    .venv ❯ python

    >>> import fastenv
    >>> dotenv = fastenv.DotEnv("KEY1=value1", "KEY2=value2 KEY3=value3", key4="value4")
    >>> dict(dotenv)
    {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4'}
    ```

### Calling `DotEnv` instances

`DotEnv` instances can also get or set environment variables when they are [called](https://docs.python.org/3/reference/expressions.html#calls).

#### Getting variables with calls

A single positional argument with a key only will return the value, or `None` if the value is unset. `DotEnv` instances also have a `getenv` method, corresponding to `os.getenv`, that allows an optional default argument to be passed in.

Multiple positional arguments (and multi-variable strings) with keys only will return a mapping of the keys and values from the `DotEnv` instance.

!!!example "Getting variables from a `DotEnv` instance"

    ```py
    .venv ❯ python

    >>> import fastenv
    >>> dotenv = fastenv.DotEnv("KEY1=value1")
    >>> dotenv("KEY1")
    'value1'
    >>> dotenv("NOT_SET")
    >>> dotenv.getenv("NOT_SET", "default_value")
    'default_value'
    >>> dotenv("KEY1", "NOT_SET NOT_SET_EITHER")
    {'KEY1': 'value1', 'NOT_SET': None, 'NOT_SET_EITHER': None}
    ```

#### Setting variables

`DotEnv` instance calls with `"KEY=value"` strings or keyword arguments will not only set variables, but also return a dict of variables that were set.

If no return value is needed, the `setenv` method can be used.

!!!example "Setting variables in a `DotEnv` instance"

    ```py
    .venv ❯ python

    >>> import fastenv
    >>> dotenv = fastenv.DotEnv()
    >>> dotenv("KEY1=value1", "KEY2=value2 KEY3=value3", key4="value4")
    {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4'}
    >>> dotenv.setenv(key5="value5")
    >>> dict(dotenv)
    {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4', 'KEY5': 'value5'}
    ```

#### Getting and setting in the same call

Complex combinations of getting and setting can be accomplished in the same call, and the result will be returned.

!!!example "Getting and setting in the same call to a `DotEnv` instance"

    ```py
    .venv ❯ python

    >>> import fastenv
    >>> dotenv = fastenv.DotEnv("KEY1=value1")
    >>> dotenv("KEY1", "KEY2=value2 KEY3=value3", key4="value4")
    {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4'}
    ```

#### Deleting variables

Single variables can be deleted by using `del`.

Multiple variables can be deleted by calling the `delenv` method.

!!!example "Deleting variables from a `DotEnv` instance"

    ```py
    .venv ❯ python

    >>> import fastenv
    >>> dotenv = fastenv.DotEnv()
    >>> dotenv("KEY1=value1", "KEY2=value2 KEY3=value3", key4="value4")
    {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4'}
    >>> del dotenv["KEY4"]
    >>> dotenv.delenv("KEY1", "KEY2", "KEY3")
    >>> len(dotenv)
    0
    ```

## Tips

!!!tip "Formatting environment variables"

    In general, environment variables should be formatted with valid shell syntax. Variable values that contain spaces should be quoted to ensure correct parsing.

    The example below demonstrates how to set a JSON object as an environment variable from the command line. See the guide to [understanding JSON schema](https://json-schema.org/understanding-json-schema/index.html) for many helpful examples of how JSON data types correspond to Python data types.

    ```sh
    ❯ JSON_EXAMPLE={"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}
    zsh: parse error near `}`

    ❯ JSON_EXAMPLE='{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}'

    ❯ echo $JSON_EXAMPLE
    {"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}
    ```

!!!tip "Handling type errors"

    Environment variable keys and values should be strings.

    If non-string positional arguments ("args") are passed to a `DotEnv` instance, it will raise a `TypeError`, rather than attempting to handle the args. This is because args can be used either to get or set variables, and it can be challenging to infer the user's intent when non-string args are used in this situation. Are they passing in a list of args to get? Or maybe the value is intended to be a JSON array? Or maybe the user accidentally passed in a dict of keys and values to set directly, instead of unpacking a dict into kwargs?

    For keyword arguments ("kwargs"), the situation is a little easier, because kwargs only set variables. Non-string kwarg values will be converted to strings.

    ```py
    .venv ❯ python

    >>> import fastenv
    >>> dotenv = fastenv.DotEnv(incorrect_type=[1, 2, 3])
    >>> dict(dotenv)
    {'INCORRECT_TYPE': '[1, 2, 3]'}
    ```
