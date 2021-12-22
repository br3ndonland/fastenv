from __future__ import annotations

import os
import shlex
from typing import Iterator, MutableMapping

import anyio

from fastenv.utilities import logger


class DotEnv(MutableMapping):
    __slots__ = "_data", "source"

    def __init__(self, *args: str, **kwargs: str) -> None:
        self._data: MutableMapping[str, str] = {}
        self.source: anyio.Path | list[anyio.Path] | None = None
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

    def __str__(self) -> str:
        return "".join(
            f"{key}={shlex.quote(value)}\n" for key, value in self._data.items()
        )

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

    def _sort_dotenv(self) -> None:
        self._data = dict(sorted(self._data.items()))

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
            if self.getenv(key) is not None and os.getenv(key) is not None:
                self.__delitem__(key)


async def find_dotenv(filename: os.PathLike[str] | str = ".env") -> anyio.Path:
    """Find a dotenv file, starting in the current directory, and walking
    upwards until a file with the given name is found. Returns the path
    to the file if found, or raises `FileNotFoundError` if not found.
    """
    starting_dir = await anyio.Path.cwd()
    if await (file_in_starting_dir := starting_dir.joinpath(filename)).is_file():
        return await file_in_starting_dir.resolve(strict=True)
    file_to_find = anyio.Path(filename)
    for parent in starting_dir.parents:
        async for file_in_parent_dir in parent.iterdir():
            if file_in_parent_dir.name == file_to_find.name:
                return await file_in_parent_dir.resolve(strict=True)
    raise FileNotFoundError(f"Could not find {filename}")


async def _set_dotenv_source(
    *sources: os.PathLike[str] | str,
    find_source: bool = False,
    raise_exceptions: bool = True,
) -> anyio.Path | list[anyio.Path]:
    if len(sources) == 1:
        return (
            await find_dotenv(*sources)
            if find_source
            else await anyio.Path(*sources).resolve(strict=raise_exceptions)
        )
    return [
        await find_dotenv(source)
        if find_source
        else await anyio.Path(source).resolve(strict=raise_exceptions)
        for source in sources
    ]


async def _read_dotenv_source(
    source: anyio.Path | list[anyio.Path],
    *,
    encoding: str | None = "utf-8",
    sort_dotenv: bool = False,
) -> DotEnv:
    if isinstance(source, anyio.Path):
        dotenv = DotEnv(await source.read_text(encoding=encoding))
    else:
        source_contents: list[str] = [
            await source_item.read_text(encoding=encoding) for source_item in source
        ]
        dotenv = DotEnv(*iter(source_contents))
    if sort_dotenv:
        dotenv._sort_dotenv()
    return dotenv


async def load_dotenv(
    *sources: os.PathLike[str] | str,
    encoding: str | None = "utf-8",
    find_source: bool = False,
    raise_exceptions: bool = True,
    sort_dotenv: bool = False,
) -> DotEnv:
    """Load environment variables from one or more files into a `DotEnv` model."""
    try:
        dotenv_source = await _set_dotenv_source(
            *sources, find_source=find_source, raise_exceptions=raise_exceptions
        )
        dotenv = await _read_dotenv_source(
            dotenv_source, encoding=encoding, sort_dotenv=sort_dotenv
        )
        dotenv.source = dotenv_source
        logger.info(f"fastenv loaded {len(dotenv)} variables from {dotenv.source}")
        return dotenv
    except Exception as e:
        logger.error(f"fastenv error: {e.__class__.__qualname__} {e}")
        if raise_exceptions:
            raise
    return DotEnv()


async def dotenv_values(
    source: DotEnv | os.PathLike[str] | str = ".env",
    *,
    encoding: str | None = "utf-8",
    find_source: bool = False,
    raise_exceptions: bool = True,
    sort_dotenv: bool = False,
) -> dict[str, str]:
    """Serialize a `DotEnv` source into a dictionary."""
    if isinstance(source, DotEnv):
        if sort_dotenv:
            source._sort_dotenv()
        return dict(source)
    dotenv = await load_dotenv(
        source,
        encoding=encoding,
        find_source=find_source,
        raise_exceptions=raise_exceptions,
        sort_dotenv=sort_dotenv,
    )
    return dict(dotenv)


async def dump_dotenv(
    source: DotEnv | str,
    destination: os.PathLike[str] | str = ".env",
    *,
    encoding: str | None = "utf-8",
    raise_exceptions: bool = True,
    sort_dotenv: bool = False,
) -> anyio.Path:
    """Dump a `DotEnv` model to a file."""
    try:
        if isinstance(source, DotEnv) and sort_dotenv:
            source._sort_dotenv()
        dotenv_path = anyio.Path(destination)
        await dotenv_path.write_text(str(source), encoding=encoding)
        logger.info(f"fastenv dumped to {dotenv_path}")
        return await dotenv_path.resolve(strict=raise_exceptions)
    except Exception as e:
        logger.error(f"fastenv error: {e.__class__.__qualname__} {e}")
        if raise_exceptions:
            raise
    return dotenv_path
