"""fastenv

Unified environment variable and settings management for FastAPI and beyond.

https://github.com/br3ndonland/fastenv
"""

try:
    from .cloud.object_storage import ObjectStorageClient, ObjectStorageConfig
except ImportError:  # pragma: no cover
    pass
from .dotenv import (
    DotEnv,
    dotenv_values,
    dump_dotenv,
    find_dotenv,
    load_dotenv,
)

try:
    from .settings.pydantic_settings import BaseSettings, SettingsConfigDict
    from .settings.pydantic_settings_providers import (
        JsonConfigSettingsSource,
        NestedSecretsSettingsSource,
        PyprojectTomlConfigSettingsSource,
        TomlConfigSettingsSource,
    )
    from .settings.pydantic_settings_sources import (
        DotEnvSettingsSource,
        EnvSettingsSource,
        ForceDecode,
        IncompleteFieldDefinitionWarning,
        InitSettingsSource,
        NoDecode,
        PydanticBaseSettingsSource,
        SecretsSettingsSource,
        SettingsError,
    )
except ModuleNotFoundError as e:  # pragma: no cover
    if e.name != "pydantic":
        raise

try:
    from .settings.starlette_config import Config as StarletteConfig
except ModuleNotFoundError as e:  # pragma: no cover
    if e.name != "starlette":
        raise

from .utilities import parse_dotenv

__all__ = (
    "BaseSettings",
    "DotEnv",
    "DotEnvSettingsSource",
    "EnvSettingsSource",
    "ForceDecode",
    "IncompleteFieldDefinitionWarning",
    "InitSettingsSource",
    "JsonConfigSettingsSource",
    "NestedSecretsSettingsSource",
    "NoDecode",
    "ObjectStorageClient",
    "ObjectStorageConfig",
    "PydanticBaseSettingsSource",
    "PyprojectTomlConfigSettingsSource",
    "SecretsSettingsSource",
    "SettingsConfigDict",
    "SettingsError",
    "StarletteConfig",
    "TomlConfigSettingsSource",
    "dotenv_values",
    "dump_dotenv",
    "find_dotenv",
    "load_dotenv",
    "parse_dotenv",
)
__version__ = "0.9.0"
