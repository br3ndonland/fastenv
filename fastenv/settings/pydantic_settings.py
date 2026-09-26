"""Pydantic settings models composed from independent value sources.

Written from the public API contract, without using pydantic-settings code.
"""

# Settings source values intentionally remain unvalidated until BaseModel.__init__.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import inspect
import warnings
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict

from .pydantic_settings_sources import (
    _DEFER_SETTINGS_IO,  # pyright: ignore[reportPrivateUsage]
    DefaultSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsError,
    canonicalize_inputs,
    deep_merge,
)

PathType = str | PathLike[str] | Sequence[str | PathLike[str]]
SettingsSource = (
    PydanticBaseSettingsSource
    | Callable[[], dict[str, Any] | Awaitable[dict[str, Any]]]
)


class SettingsConfigDict(ConfigDict, total=False):
    """Pydantic model configuration with settings source options."""

    case_sensitive: bool
    nested_model_default_partial_update: bool
    env_prefix: str
    env_prefix_target: Literal["variable", "alias", "all"]
    env_file: PathType | None
    env_file_encoding: str | None
    env_ignore_empty: bool
    env_nested_delimiter: str | None
    env_nested_max_split: int | None
    env_parse_none_str: str | None
    env_parse_enums: bool | None
    dotenv_filtering: Literal["only_existing", "match_prefix"] | None
    enable_decoding: bool
    secrets_dir: PathType | None
    secrets_dir_missing: Literal["ok", "warn", "error"]
    secrets_dir_max_size: int
    secrets_case_sensitive: bool
    secrets_nested_delimiter: str | None
    secrets_nested_subdir: bool
    secrets_prefix: str
    json_file: PathType | None
    json_file_encoding: str | None
    toml_file: PathType | None
    toml_table_header: tuple[str, ...]
    pyproject_toml_depth: int
    pyproject_toml_table_header: tuple[str, ...]


_SETTINGS_KEYS = (
    SettingsConfigDict.__annotations__.keys() - ConfigDict.__annotations__.keys()
)
_ENV_FILE_DEFAULT = Path("")
_SOURCE_OVERRIDE_KEYS = (
    "case_sensitive",
    "nested_model_default_partial_update",
    "env_prefix",
    "env_prefix_target",
    "env_file_encoding",
    "env_ignore_empty",
    "env_nested_delimiter",
    "env_nested_max_split",
    "env_parse_none_str",
    "env_parse_enums",
    "secrets_dir",
)


@dataclass
class _PreparedSettings:
    settings_cls: type[BaseSettings]
    instance: BaseSettings | None = None


_PREPARED_SETTINGS: ContextVar[_PreparedSettings | None] = ContextVar(
    "fastenv_prepared_settings", default=None
)


class _SettingsState:
    """Compose source results identically for synchronous and async loads."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        self.settings_cls: type[BaseSettings] = settings_cls
        self.state: dict[str, Any] = {}
        self.source_data: dict[str, dict[str, Any]] = {}
        self.defaults: dict[str, Any] = {}

    def prepare(self, source: SettingsSource) -> None:
        if isinstance(source, PydanticBaseSettingsSource):
            source._set_current_state(self.state.copy())  # pyright: ignore[reportPrivateUsage]
            source._set_settings_sources_data(self.source_data.copy())  # pyright: ignore[reportPrivateUsage]

    def add(self, source: SettingsSource, data: dict[str, Any]) -> None:
        canonical = canonicalize_inputs(self.settings_cls, data)
        if isinstance(source, DefaultSettingsSource):
            self.defaults = canonical
        name = getattr(source, "__name__", type(source).__name__)
        self.source_data[name] = data
        self.state = deep_merge(canonical, self.state)

    def values(self) -> dict[str, Any]:
        # Leave unchanged defaults to Pydantic, preserving unset-field semantics.
        return {
            key: value
            for key, value in self.state.items()
            if key not in self.defaults or value != self.defaults[key]
        }


class BaseSettings(BaseModel):
    """Validate settings from init values, environment, dotenv, and secrets.

    Sources are ordered from highest to lowest priority. Pydantic supplies
    final field defaults.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(  # pyright: ignore[reportIncompatibleVariableOverride]
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_default=True,
        case_sensitive=False,
        env_prefix="",
        env_prefix_target="variable",
        nested_model_default_partial_update=False,
        env_file=None,
        env_file_encoding=None,
        env_ignore_empty=False,
        env_nested_delimiter=None,
        env_nested_max_split=None,
        env_parse_none_str=None,
        env_parse_enums=None,
        json_file=None,
        json_file_encoding=None,
        toml_file=None,
        secrets_dir=None,
        protected_namespaces=(
            "model_validate",
            "model_dump",
            "settings_customise_sources",
        ),
        enable_decoding=True,
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Pydantic consumes its own config keywords before invoking this hook.
        # Handle settings keywords here without modifying Pydantic's internals.
        for key in tuple(kwargs):
            if key in _SETTINGS_KEYS:
                cls.model_config[key] = kwargs.pop(key)
        super().__init_subclass__(**kwargs)

    def __new__(cls, /, *_args: Any, **_kwargs: Any) -> Self:
        instance = super().__new__(cls)
        prepared = _PREPARED_SETTINGS.get()
        # Bind before a custom initializer can construct another instance.
        if (
            prepared is not None
            and prepared.settings_cls is cls
            and prepared.instance is None
        ):
            prepared.instance = instance
        return instance

    def __init__(
        __settings_self__,  # pyright: ignore[reportSelfClsParameterName]
        _case_sensitive: bool | None = None,
        _nested_model_default_partial_update: bool | None = None,
        _env_prefix: str | None = None,
        _env_prefix_target: Literal["variable", "alias", "all"] | None = None,
        _env_file: PathType | None = _ENV_FILE_DEFAULT,
        _env_file_encoding: str | None = None,
        _env_ignore_empty: bool | None = None,
        _env_nested_delimiter: str | None = None,
        _env_nested_max_split: int | None = None,
        _env_parse_none_str: str | None = None,
        _env_parse_enums: bool | None = None,
        _secrets_dir: PathType | None = None,
        **values: Any,
    ) -> None:
        settings_cls = type(__settings_self__)
        prepared = _PREPARED_SETTINGS.get()
        if prepared is not None and prepared.instance is __settings_self__:
            # Consume the bypass before validation can construct nested models.
            _ = _PREPARED_SETTINGS.set(None)
            super().__init__(**values)
            return
        options = settings_cls._settings_options(
            {
                "_case_sensitive": _case_sensitive,
                "_nested_model_default_partial_update": _nested_model_default_partial_update,
                "_env_prefix": _env_prefix,
                "_env_prefix_target": _env_prefix_target,
                "_env_file": _env_file,
                "_env_file_encoding": _env_file_encoding,
                "_env_ignore_empty": _env_ignore_empty,
                "_env_nested_delimiter": _env_nested_delimiter,
                "_env_nested_max_split": _env_nested_max_split,
                "_env_parse_none_str": _env_parse_none_str,
                "_env_parse_enums": _env_parse_enums,
                "_secrets_dir": _secrets_dir,
            }
        )
        # A custom async source hook may construct another settings model.
        # An explicit synchronous constructor retains its normal file behavior.
        token = _DEFER_SETTINGS_IO.set(False)
        try:
            sources = settings_cls._settings_sources(values, options)
        finally:
            _DEFER_SETTINGS_IO.reset(token)
        state = _SettingsState(settings_cls)
        for source in sources:
            state.prepare(source)
            data = source()
            if inspect.isawaitable(data):
                if inspect.iscoroutine(data):
                    data.close()
                raise SettingsError(
                    "Asynchronous settings sources require await Settings.load()"
                )
            state.add(source, data)
        super().__init__(**state.values())

    @classmethod
    async def load(cls, /, **values: Any) -> Self:
        """Load sources asynchronously, then validate a new settings instance.

        Accept the same field values and source overrides as the constructor.
        Sources run in priority order so custom sources can inspect prior values.
        File sources use async I/O. Custom sources may return an awaitable or
        override their async ``load`` method.
        """
        options = cls._settings_options(values)
        token = _DEFER_SETTINGS_IO.set(True)
        try:
            sources = cls._settings_sources(values, options)
        finally:
            _DEFER_SETTINGS_IO.reset(token)
        state = _SettingsState(cls)
        for source in sources:
            state.prepare(source)
            data = (
                await source.load()
                if isinstance(source, PydanticBaseSettingsSource)
                else source()
            )
            if inspect.isawaitable(data):
                data = await data
            state.add(source, data)
        prepared_token = _PREPARED_SETTINGS.set(_PreparedSettings(cls))
        try:
            # Custom constructors receive the ordinary, still unvalidated inputs.
            return cls(**state.values())
        finally:
            _PREPARED_SETTINGS.reset(prepared_token)

    @classmethod
    def _settings_options(cls, values: dict[str, Any]) -> dict[str, Any]:
        options = dict(cls.model_config)
        for key in _SOURCE_OVERRIDE_KEYS:
            override = values.pop(f"_{key}", None)
            if override is not None:
                options[key] = override
        env_file = values.pop("_env_file", _ENV_FILE_DEFAULT)
        if env_file != _ENV_FILE_DEFAULT:
            options["env_file"] = env_file
        return options

    @classmethod
    def _settings_sources(
        cls,
        values: dict[str, Any],
        options: dict[str, Any],
    ) -> tuple[SettingsSource, ...]:
        env_options = {
            key: options.get(key)
            for key in (
                "case_sensitive",
                "env_prefix",
                "env_prefix_target",
                "env_ignore_empty",
                "env_nested_delimiter",
                "env_nested_max_split",
                "env_parse_none_str",
                "env_parse_enums",
            )
        }
        partial_update = options["nested_model_default_partial_update"]
        init = InitSettingsSource(
            cls, values, nested_model_default_partial_update=partial_update
        )
        env = EnvSettingsSource(cls, **env_options)
        dotenv = DotEnvSettingsSource(
            cls,
            env_file=options["env_file"],
            env_file_encoding=options["env_file_encoding"],
            **env_options,
        )
        secrets = SecretsSettingsSource(
            cls,
            secrets_dir=options["secrets_dir"],
            case_sensitive=options["case_sensitive"],
            env_prefix=options["env_prefix"],
            env_prefix_target=options["env_prefix_target"],
        )
        sources = cls.settings_customise_sources(
            cls,
            init_settings=init,
            env_settings=env,
            dotenv_settings=dotenv,
            file_secret_settings=secrets,
        )
        from .pydantic_settings_providers import (
            JsonConfigSettingsSource,
            PyprojectTomlConfigSettingsSource,
            TomlConfigSettingsSource,
        )

        for source_cls, keys in (
            (JsonConfigSettingsSource, ("json_file", "json_file_encoding")),
            (TomlConfigSettingsSource, ("toml_file", "toml_table_header")),
            (
                PyprojectTomlConfigSettingsSource,
                ("pyproject_toml_depth", "pyproject_toml_table_header"),
            ),
        ):
            if not any(isinstance(source, source_cls) for source in sources):
                for key in keys:
                    if options.get(key) is not None:
                        warnings.warn(
                            f"{key} is configured without {source_cls.__name__}. "
                            + "Add the source in settings_customise_sources to load it.",
                            UserWarning,
                            stacklevel=3,
                        )
        return (
            *sources,
            DefaultSettingsSource(
                cls, nested_model_default_partial_update=partial_update
            ),
        )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],  # pyright: ignore[reportUnusedParameter]
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[SettingsSource, ...]:
        """Choose and order sources, from highest to lowest priority."""
        return init_settings, env_settings, dotenv_settings, file_secret_settings
