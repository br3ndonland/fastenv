from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING, TypeVar, overload

import anyio
import starlette.config

from fastenv.utilities import logger, parse_dotenv, read_toml_file

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from typing import Any, Self

T = TypeVar("T")


class StarletteConfig(starlette.config.Config):
    """Starlette settings with multiple dotenv files and TOML metadata.

    Environment variables take priority over dotenv files, which take priority
    over TOML values. Later dotenv files override earlier ones. Pass files to the
    constructor in synchronous code, or await ``load`` to create an instance
    asynchronously. Neither option modifies the environment. Retrieve settings
    synchronously. By default, file errors are raised. Set
    ``raise_exceptions=False`` to log and skip failed sources.
    """

    # Native TOML values broaden Starlette's string-only storage.
    file_values: dict[str, object]  # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        env_file: Sequence[os.PathLike[str] | str]
        | os.PathLike[str]
        | str
        | None = None,
        environ: Mapping[str, str] = starlette.config.environ,
        env_prefix: str = "",
        encoding: str = "utf-8",
        *,
        toml_file: os.PathLike[str] | str | None = None,
        toml_table: str = "project",
        raise_exceptions: bool = True,
    ) -> None:
        """Load files with AnyIO before returning, or use only the environment.

        File loading requires a thread without a running event loop. In async
        code, use ``await StarletteConfig.load(...)`` instead.
        """
        super().__init__(environ=environ, env_prefix=env_prefix)
        if env_file is not None or toml_file is not None:
            anyio.run(
                partial(
                    self._load_files,
                    env_file,
                    encoding=encoding,
                    toml_file=toml_file,
                    toml_table=toml_table,
                    raise_exceptions=raise_exceptions,
                )
            )

    @classmethod
    async def load(
        cls,
        env_file: Sequence[os.PathLike[str] | str]
        | os.PathLike[str]
        | str
        | None = None,
        environ: Mapping[str, str] = starlette.config.environ,
        env_prefix: str = "",
        encoding: str = "utf-8",
        *,
        toml_file: os.PathLike[str] | str | None = None,
        toml_table: str = "project",
        raise_exceptions: bool = True,
    ) -> Self:
        """Load dotenv and TOML files asynchronously into a new config instance."""
        config = cls(environ=environ, env_prefix=env_prefix)
        await config._load_files(
            env_file,
            encoding=encoding,
            toml_file=toml_file,
            toml_table=toml_table,
            raise_exceptions=raise_exceptions,
        )
        return config

    async def _load_files(
        self,
        env_file: Sequence[os.PathLike[str] | str]
        | os.PathLike[str]
        | str
        | None = None,
        *,
        encoding: str = "utf-8",
        toml_file: os.PathLike[str] | str | None = None,
        toml_table: str = "project",
        raise_exceptions: bool = True,
    ) -> None:
        """Read TOML and dotenv sources in order for both loading entry points."""
        if toml_file is not None:
            try:
                self.file_values.update(
                    await read_toml_file(toml_file, table=toml_table)
                )
            except (OSError, ValueError, LookupError, TypeError) as e:
                logger.error(
                    f"fastenv error reading {toml_file}: {e.__class__.__qualname__} {e}"
                )
                if raise_exceptions:
                    raise
        files = (
            (env_file,)
            if isinstance(env_file, (str, os.PathLike))
            else env_file
            if env_file is not None
            else ()
        )
        for file in files:
            try:
                path = anyio.Path(file)
                content = await path.read_text(encoding=encoding)
                self.file_values.update(parse_dotenv(content))
            except (OSError, ValueError, LookupError, TypeError) as e:
                logger.error(
                    f"fastenv error reading {file}: {e.__class__.__qualname__} {e}"
                )
                if raise_exceptions:
                    raise

    @overload
    def __call__(
        self,
        key: str,
        cast: Callable[[Any], T],  # pyright: ignore[reportExplicitAny]
        default: object = ...,
    ) -> T: ...

    @overload
    def __call__(
        self, key: str, cast: None = None, default: object = ...
    ) -> object: ...

    # Uncast TOML values can have any native type, unlike Starlette's strings.
    def __call__(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        key: str,
        cast: Callable[[Any], object] | None = None,  # pyright: ignore[reportExplicitAny]
        default: object = starlette.config.undefined,
    ) -> object:
        return self.get(key, cast, default)  # pyright: ignore[reportAny]
