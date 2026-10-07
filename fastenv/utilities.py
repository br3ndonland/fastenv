from __future__ import annotations

import logging
import shlex
import tomllib
from typing import TYPE_CHECKING, cast

import anyio

if TYPE_CHECKING:
    from os import PathLike

logger = logging.getLogger("fastenv")


def parse_dotenv_args(*args: str) -> list[str]:
    if any(not isinstance(arg, str) for arg in args):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("Arguments passed to DotEnv instances should be strings")
    parsed_args: list[str] = []
    for arg in args:
        parsed_args += shlex.split(arg, comments=True, posix=True)
    return parsed_args


def parse_dotenv(*args: str) -> tuple[tuple[str, str], ...]:
    """Parse dotenv strings without modifying the process environment."""
    return tuple(
        (split_arg[0].strip(" \n\"'").upper(), split_arg[1].strip(" \n\"'"))
        for arg in parse_dotenv_args(*args)
        if len(split_arg := arg.split(sep="=", maxsplit=1)) == 2
    )


async def read_toml_file(
    toml_file: PathLike[str] | str = "pyproject.toml", table: str = "project"
) -> dict[str, object]:
    """Read a TOML table asynchronously, preserving native values and uppercase keys."""
    path = anyio.Path(toml_file)
    # Preserve newlines so the parser can reject invalid TOML control characters.
    content = await path.read_bytes()
    data: dict[str, object] = tomllib.loads(content.decode("utf-8"))
    values = data[table]
    if not isinstance(values, dict):
        raise TypeError(f"TOML entry {table!r} must be a table")
    return {
        key.upper(): value for key, value in cast("dict[str, object]", values).items()
    }
