from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastenv import __version__

    from .pydantic_settings import BaseSettings, SettingsConfigDict
    from .pydantic_settings_providers import (
        JsonConfigSettingsSource,
        NestedSecretsSettingsSource,
        PyprojectTomlConfigSettingsSource,
        TomlConfigSettingsSource,
    )
    from .pydantic_settings_sources import (
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


_EXPORT_MODULES: dict[str, str] = {
    "__version__": "fastenv",
    "BaseSettings": ".pydantic_settings",
    "SettingsConfigDict": ".pydantic_settings",
    "JsonConfigSettingsSource": ".pydantic_settings_providers",
    "NestedSecretsSettingsSource": ".pydantic_settings_providers",
    "PyprojectTomlConfigSettingsSource": ".pydantic_settings_providers",
    "TomlConfigSettingsSource": ".pydantic_settings_providers",
    "DotEnvSettingsSource": ".pydantic_settings_sources",
    "EnvSettingsSource": ".pydantic_settings_sources",
    "ForceDecode": ".pydantic_settings_sources",
    "IncompleteFieldDefinitionWarning": ".pydantic_settings_sources",
    "InitSettingsSource": ".pydantic_settings_sources",
    "NoDecode": ".pydantic_settings_sources",
    "PydanticBaseSettingsSource": ".pydantic_settings_sources",
    "SecretsSettingsSource": ".pydantic_settings_sources",
    "SettingsError": ".pydantic_settings_sources",
}


def __getattr__(name: str) -> Any:  # pyright: ignore[reportAny, reportExplicitAny]
    """Load Pydantic exports only when requested, keeping extras independent."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    value: Any = getattr(module, name)  # pyright: ignore[reportAny, reportExplicitAny]
    globals()[name] = value
    return value  # pyright: ignore[reportAny]


__all__ = (
    "BaseSettings",
    "DotEnvSettingsSource",
    "EnvSettingsSource",
    "ForceDecode",
    "IncompleteFieldDefinitionWarning",
    "InitSettingsSource",
    "JsonConfigSettingsSource",
    "NestedSecretsSettingsSource",
    "NoDecode",
    "PydanticBaseSettingsSource",
    "PyprojectTomlConfigSettingsSource",
    "SecretsSettingsSource",
    "SettingsConfigDict",
    "SettingsError",
    "TomlConfigSettingsSource",
    "__version__",
)
