"""TODO:

- Logging here fo sho
- Maybe put object download stuff here for s3 etc?
- Maybe use aiofiles? Starlette allows any version, aioaws allows 'aiofiles>=0.5.0'
"""
import importlib
import logging
from os import PathLike
from types import ModuleType
from typing import Callable, Optional, TextIO, Union

try:
    aioaws: Optional[ModuleType] = importlib.import_module("aioaws")
except ImportError:
    aioaws = None

try:
    aiofiles: Optional[ModuleType] = importlib.import_module("aiofiles")
except ImportError:
    aiofiles = None

logger = logging.getLogger("fastenv")


def load_toml(
    file: Union[PathLike, TextIO], tool: str = "poetry", uppercase_keys: bool = False
) -> dict:
    """Load a TOML file and return the specified configuration section.

    TODO: explain tool section

    If `uppercase_keys` is `True`, dict keys will be uppercased,
    allowing them to be easily set as environment variables.
    """
    try:
        toml = importlib.import_module("rtoml")
    except ImportError:
        toml = importlib.import_module("toml")
    toml_load: Callable = getattr(toml, "load")
    toml_dict: dict = toml_load(file)
    return {
        key.upper() if uppercase_keys else key: toml_dict.get(key)
        for key in toml_dict["tool"][tool]
    }
