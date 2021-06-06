"""TODO: I'm thinking the primary dotenv functionality will be here

TODO: instead of `get_key`, `set_key`, `unset_key`, use calls like Starlette `Config`
"""
import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import Iterator, Optional


class DotEnv(MutableMapping):
    def __init__(self) -> None:
        self._environ: dict[str, str] = {}

    def __call__(self, variable: str) -> None:
        if variable in self._environ:
            # TODO: dotenv("VARIABLE") = value (get)
            self.__getitem__(variable)
        else:
            # TODO: dotenv("VARIABLE=value") or dotenv(variable=value) -> set
            self.__setitem__(variable)

    def __getitem__(self, key: str) -> Optional[str]:
        return self._environ.get(key)

    def __setitem__(self, *args: str, **kwargs: str) -> None:
        for arg in args:
            key, value = arg.split(sep="=", maxsplit=1)
            self.set_variable(key, value)
        for kwarg in kwargs:
            self.set_variable(kwarg, kwargs[kwarg])

    def __delitem__(self, key: str) -> None:
        del os.environ[key]
        del self._environ[key]

    def __iter__(self) -> Iterator:
        return iter(self._environ)

    def __len__(self) -> int:
        return len(self._environ)

    def set_variable(self, key: str, value: str) -> None:
        key = key.strip().upper()
        value = value.strip(" \"'")
        os.environ[key] = value
        self._environ[key] = value


async def dump_dotenv(dotenv: DotEnv, raise_exceptions: bool = False) -> Path:
    """Dump a `DotEnv` model to a file."""
    pass


async def load_dotenv(uri: os.PathLike[str], raise_exceptions: bool = False) -> DotEnv:
    """Load environment variables into a `DotEnv` model."""
    pass


async def dotenv_values() -> dict:
    """TODO"""
    pass
