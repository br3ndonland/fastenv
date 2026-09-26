"""Optional Starlette and Pydantic integrations for application settings."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastenv import __version__

    from .cli import (
        CLI_SUPPRESS,
        CliApp,
        CliDualFlag,
        CliExplicitFlag,
        CliImplicitFlag,
        CliMutuallyExclusiveGroup,
        CliPositionalArg,
        CliSettingsSource,
        CliSubCommand,
        CliSuppress,
        CliToggleFlag,
        CliUnknownArgs,
        get_subcommand,
    )
    from .main import BaseSettings, SettingsConfigDict
    from .providers import (
        JsonConfigSettingsSource,
        NestedSecretsSettingsSource,
        PyprojectTomlConfigSettingsSource,
        TomlConfigSettingsSource,
        YamlConfigSettingsSource,
    )
    from .sources import (
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
    "CLI_SUPPRESS": ".cli",
    "CliApp": ".cli",
    "CliDualFlag": ".cli",
    "CliExplicitFlag": ".cli",
    "CliImplicitFlag": ".cli",
    "CliMutuallyExclusiveGroup": ".cli",
    "CliPositionalArg": ".cli",
    "CliSettingsSource": ".cli",
    "CliSubCommand": ".cli",
    "CliSuppress": ".cli",
    "CliToggleFlag": ".cli",
    "CliUnknownArgs": ".cli",
    "get_subcommand": ".cli",
    "BaseSettings": ".main",
    "SettingsConfigDict": ".main",
    "JsonConfigSettingsSource": ".providers",
    "NestedSecretsSettingsSource": ".providers",
    "PyprojectTomlConfigSettingsSource": ".providers",
    "TomlConfigSettingsSource": ".providers",
    "YamlConfigSettingsSource": ".providers",
    "DotEnvSettingsSource": ".sources",
    "EnvSettingsSource": ".sources",
    "ForceDecode": ".sources",
    "IncompleteFieldDefinitionWarning": ".sources",
    "InitSettingsSource": ".sources",
    "NoDecode": ".sources",
    "PydanticBaseSettingsSource": ".sources",
    "SecretsSettingsSource": ".sources",
    "SettingsError": ".sources",
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
    "CLI_SUPPRESS",
    "BaseSettings",
    "CliApp",
    "CliDualFlag",
    "CliExplicitFlag",
    "CliImplicitFlag",
    "CliMutuallyExclusiveGroup",
    "CliPositionalArg",
    "CliSettingsSource",
    "CliSubCommand",
    "CliSuppress",
    "CliToggleFlag",
    "CliUnknownArgs",
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
    "YamlConfigSettingsSource",
    "__version__",
    "get_subcommand",
)
