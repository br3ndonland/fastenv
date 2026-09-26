from __future__ import annotations

import os
from typing import TYPE_CHECKING, TypeVar, overload

import starlette.config

from fastenv.utilities import _parse_dotenv, _read_toml_file, logger

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from typing import Any

T = TypeVar("T")


class Config(starlette.config.Config):
    """Starlette settings with multiple dotenv files and TOML metadata.

    Environment variables take priority over dotenv files, which take priority
    over TOML values. Later dotenv files override earlier ones. File loading is
    synchronous and does not modify the environment. By default, file errors
    are raised. Set ``raise_exceptions=False`` to log and skip failed sources.
    """

    file_values: dict[str, Any]  # pyright: ignore[reportExplicitAny]

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
        super().__init__(environ=environ, env_prefix=env_prefix)
        if toml_file is not None:
            try:
                self.file_values.update(_read_toml_file(toml_file, table=toml_table))
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
                self.file_values.update(self._read_file(file, encoding))
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

    def _read_file(
        self, file_name: os.PathLike[str] | str, encoding: str = "utf-8"
    ) -> dict[str, str]:
        with open(file_name, encoding=encoding) as source:
            return dict(_parse_dotenv(source.read()))
