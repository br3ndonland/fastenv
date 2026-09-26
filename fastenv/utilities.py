from __future__ import annotations

import logging
import shlex
import tomllib
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from os import PathLike

__all__ = ("_parse_dotenv", "_parse_dotenv_args", "_read_toml_file", "logger")

logger = logging.getLogger("fastenv")


def _parse_dotenv_args(*args: str) -> list[str]:
    if any(not isinstance(arg, str) for arg in args):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("Arguments passed to DotEnv instances should be strings")
    parsed_args: list[str] = []
    for arg in args:
        parsed_args += shlex.split(arg, comments=True, posix=True)
    return parsed_args


def _parse_dotenv(*args: str) -> tuple[tuple[str, str], ...]:
    """Parse dotenv strings without modifying the process environment."""
    return tuple(
        (split_arg[0].strip(" \n\"'").upper(), split_arg[1].strip(" \n\"'"))
        for arg in _parse_dotenv_args(*args)
        if len(split_arg := arg.split(sep="=", maxsplit=1)) == 2
    )


def _read_toml_file(
    toml_file: PathLike[str] | str = "pyproject.toml", table: str = "project"
) -> dict[str, object]:
    """Read a TOML table with uppercase keys and preserve native values."""
    with open(toml_file, "rb") as source:
        data: dict[str, object] = tomllib.load(source)
    values = data[table]
    if not isinstance(values, dict):
        raise TypeError(f"TOML entry {table!r} must be a table")
    return {
        key.upper(): value for key, value in cast("dict[str, object]", values).items()
    }
