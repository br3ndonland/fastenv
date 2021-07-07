from __future__ import annotations

import os
import pathlib
import shlex
from typing import Iterator, MutableMapping


class DotEnv(MutableMapping):
    __slots__ = "_data"

    def __init__(self, *args: str, **kwargs: str) -> None:
        self._data: MutableMapping[str, str] = {}
        self.setenv(*args, **kwargs)

    def __getitem__(self, key: str) -> str | None:
        return self._data[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._data[key] = value
        os.environ[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        del os.environ[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __call__(self, *args: str, **kwargs: str) -> str | dict[str, str | None] | None:
        if self._is_single_arg_to_get(*args, **kwargs):
            return self.getenv(args[0])
        self.setenv(*args, **kwargs)
        result = {
            arg: self.getenv(arg)
            for arg in self._parse_args_to_get(*args)
            + tuple(arg[0] for arg in self._parse_args_to_set(*args))
        }
        for key in self._parse_kwargs(**kwargs):
            result[key] = self.getenv(key)
        return result or None

    def _is_single_arg_to_get(self, *args: str, **kwargs: str) -> bool:
        return (
            len(args) == 1
            and isinstance(args[0], str)
            and not args[0].startswith("#")
            and "=" not in args[0]
            and " " not in args[0]
            and not kwargs
        )

    def _parse_args(self, *args: str) -> list[str]:
        if any(not isinstance(arg, str) for arg in args):
            raise TypeError("Arguments passed to DotEnv instances should be strings")
        parsed_args: list[str] = []
        for arg in args:
            parsed_args += shlex.split(arg, comments=True, posix=True)
        return parsed_args

    def _parse_args_to_get(self, *args: str) -> tuple[str, ...]:
        parsed_args: list[str] = self._parse_args(*args)
        return tuple(a.upper() for a in parsed_args if "=" not in a)

    def _parse_args_to_set(self, *args: str) -> tuple[tuple[str, str], ...]:
        parsed_args: list[str] = self._parse_args(*args)
        return tuple(
            (split_arg[0].strip(" \n\"'").upper(), split_arg[1].strip(" \n\"'"))
            for a in parsed_args
            if len((split_arg := a.split(sep="=", maxsplit=1))) == 2
        )

    def _parse_kwargs(self, **kwargs: str) -> dict[str, str]:
        return {
            str(k).strip(" \n\"'").upper(): str(kwargs.get(k) or "").strip(" \n\"'")
            for k in kwargs
        }

    def getenv(self, key: str, default: str | None = None) -> str | None:
        """Get an environment variable from a `DotEnv` instance, or return `None` if it
        doesn't exist. The optional second argument can specify an alternate default.
        """
        return self._data.get(key, default)

    def setenv(self, *args: str, **kwargs: str) -> None:
        """Set one or more environment variables on both a `DotEnv` instance
        and `os.environ`. Variables to set can be passed in as string arguments
        (`dotenv.setenv("KEY1=value1", "KEY2=value2")`), keyword arguments, or both.

        Alternatively, `DotEnv` instance calls (`dotenv("KEY1=value1", "KEY2=value2"))`
        will not only set variables, but also return a dict of variables that were set.
        """
        for key, value in self._parse_args_to_set(*args):
            self.__setitem__(key, value)
        for key, value in self._parse_kwargs(**kwargs).items():
            self.__setitem__(key, value)

    def delenv(self, *args: str) -> None:
        """Delete one or more environment variables from both a `DotEnv` instance
        and `os.environ`. Variables to delete can be passed in as string arguments
        (`delenv("KEY1", "KEY2")`).
        """
        for key in self._parse_args_to_get(*args):
            if self.getenv(key) and os.getenv(key):
                self.__delitem__(key)


def find_dotenv(
    filename: os.PathLike[str] | str = ".env",
    starting_dir: os.PathLike[str] | str = pathlib.Path.cwd(),
) -> pathlib.Path:
    """Find a dotenv file, starting in the given directory, and
    walking upwards until a file with the given filename is found.
    """
    raise NotImplementedError("This method hasn't yet been implemented")


async def dump_dotenv(
    source: DotEnv | str,
    destination: os.PathLike[str] | str = ".env",
    *,
    encoding: str | None = "utf-8",
    raise_exceptions: bool = True,
) -> pathlib.Path:
    """Dump a `DotEnv` model to a file."""
    raise NotImplementedError("This method hasn't yet been implemented. Coming soon!")


async def load_dotenv(
    source: os.PathLike[str] | str = ".env",
    *,
    encoding: str | None = "utf-8",
    find_source: bool = False,
    raise_exceptions: bool = True,
) -> DotEnv:
    """Load environment variables from a file into a `DotEnv` model."""
    if not raise_exceptions:
        return DotEnv()
    raise NotImplementedError("File I/O hasn't yet been implemented.")


async def dotenv_values(
    source: DotEnv | os.PathLike[str] | str = ".env",
    *,
    encoding: str | None = "utf-8",
    find_source: bool = False,
    raise_exceptions: bool = True,
) -> dict[str, str]:
    """Serialize a `DotEnv` source into a dictionary."""
    if isinstance(source, DotEnv):
        return dict(source)
    dotenv = await load_dotenv(
        source,
        encoding=encoding,
        find_source=find_source,
        raise_exceptions=raise_exceptions,
    )
    return dict(dotenv)
