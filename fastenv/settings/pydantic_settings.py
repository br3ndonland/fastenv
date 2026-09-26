"""Pydantic settings models composed from independent value sources.

Written from the public API contract, without using pydantic-settings code.
"""

# Settings source values intentionally remain unvalidated until BaseModel.__init__.
# The CLI imports BaseSettings lazily, after both modules have initialized.
# pyright: reportAny=false, reportExplicitAny=false, reportImportCycles=false

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping, Sequence
from os import PathLike
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from .pydantic_settings_sources import (
    DefaultSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    canonicalize_inputs,
    deep_merge,
)

PathType = str | PathLike[str] | Sequence[str | PathLike[str]]
SettingsSource = PydanticBaseSettingsSource | Callable[[], dict[str, Any]]


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
    cli_prog_name: str | None
    cli_parse_args: bool | list[str] | tuple[str, ...] | None
    cli_parse_none_str: str | None
    cli_hide_none_type: bool
    cli_avoid_json: bool
    cli_enforce_required: bool
    cli_use_class_docs_for_groups: bool
    cli_show_env_vars: bool
    cli_exit_on_error: bool
    cli_prefix: str
    cli_flag_prefix_char: str
    cli_implicit_flags: bool | Literal["dual", "toggle"]
    cli_ignore_unknown_args: bool
    cli_kebab_case: bool | Literal["all", "no_enums"]
    cli_shortcuts: Mapping[str, str | list[str]] | None


_SETTINGS_KEYS = (
    SettingsConfigDict.__annotations__.keys() - ConfigDict.__annotations__.keys()
)
_ENV_FILE_DEFAULT = Path("")


class BaseSettings(BaseModel):
    """Validate settings from init values, environment, dotenv, and secrets.

    Sources are ordered from highest to lowest priority. CLI values, when
    enabled, precede the other sources. Pydantic supplies final field defaults.
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
        cli_prog_name=None,
        cli_parse_args=None,
        cli_parse_none_str=None,
        cli_hide_none_type=False,
        cli_avoid_json=False,
        cli_enforce_required=False,
        cli_use_class_docs_for_groups=False,
        cli_show_env_vars=False,
        cli_exit_on_error=True,
        cli_prefix="",
        cli_flag_prefix_char="-",
        cli_implicit_flags=False,
        cli_ignore_unknown_args=False,
        cli_kebab_case=False,
        cli_shortcuts=None,
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
        _cli_prog_name: str | None = None,
        _cli_parse_args: bool | list[str] | tuple[str, ...] | None = None,
        _cli_settings_source: Any = None,
        _cli_parse_none_str: str | None = None,
        _cli_hide_none_type: bool | None = None,
        _cli_avoid_json: bool | None = None,
        _cli_enforce_required: bool | None = None,
        _cli_use_class_docs_for_groups: bool | None = None,
        _cli_show_env_vars: bool | None = None,
        _cli_exit_on_error: bool | None = None,
        _cli_prefix: str | None = None,
        _cli_flag_prefix_char: str | None = None,
        _cli_implicit_flags: bool | Literal["dual", "toggle"] | None = None,
        _cli_ignore_unknown_args: bool | None = None,
        _cli_kebab_case: bool | Literal["all", "no_enums"] | None = None,
        _cli_shortcuts: Mapping[str, str | list[str]] | None = None,
        _secrets_dir: PathType | None = None,
        _build_sources: tuple[tuple[SettingsSource, ...], dict[str, Any]] | None = None,
        **values: Any,
    ) -> None:
        options = dict(__settings_self__.model_config)
        overrides = {
            "case_sensitive": _case_sensitive,
            "nested_model_default_partial_update": _nested_model_default_partial_update,
            "env_prefix": _env_prefix,
            "env_prefix_target": _env_prefix_target,
            "env_file_encoding": _env_file_encoding,
            "env_ignore_empty": _env_ignore_empty,
            "env_nested_delimiter": _env_nested_delimiter,
            "env_nested_max_split": _env_nested_max_split,
            "env_parse_none_str": _env_parse_none_str,
            "env_parse_enums": _env_parse_enums,
            "secrets_dir": _secrets_dir,
            "cli_prog_name": _cli_prog_name,
            "cli_parse_args": _cli_parse_args,
            "cli_parse_none_str": _cli_parse_none_str,
            "cli_hide_none_type": _cli_hide_none_type,
            "cli_avoid_json": _cli_avoid_json,
            "cli_enforce_required": _cli_enforce_required,
            "cli_use_class_docs_for_groups": _cli_use_class_docs_for_groups,
            "cli_show_env_vars": _cli_show_env_vars,
            "cli_exit_on_error": _cli_exit_on_error,
            "cli_prefix": _cli_prefix,
            "cli_flag_prefix_char": _cli_flag_prefix_char,
            "cli_implicit_flags": _cli_implicit_flags,
            "cli_ignore_unknown_args": _cli_ignore_unknown_args,
            "cli_kebab_case": _cli_kebab_case,
            "cli_shortcuts": _cli_shortcuts,
        }
        options.update(
            {key: value for key, value in overrides.items() if value is not None}
        )
        if _env_file != _ENV_FILE_DEFAULT:
            options["env_file"] = _env_file
        settings_cls = type(__settings_self__)
        sources = (
            _build_sources[0]
            if _build_sources is not None
            else settings_cls._settings_sources(values, options, _cli_settings_source)
        )
        state: dict[str, Any] = {}
        source_data: dict[str, dict[str, Any]] = {}
        defaults: dict[str, Any] = {}
        for source in sources:
            if isinstance(source, PydanticBaseSettingsSource):
                source._set_current_state(state.copy())  # pyright: ignore[reportPrivateUsage]
                source._set_settings_sources_data(source_data.copy())  # pyright: ignore[reportPrivateUsage]
            data = source()
            if isinstance(source, DefaultSettingsSource):
                defaults = canonicalize_inputs(settings_cls, data)
            name = getattr(source, "__name__", type(source).__name__)
            source_data[name] = data
            state = deep_merge(canonicalize_inputs(settings_cls, data), state)
        # Leave unchanged defaults to Pydantic, preserving unset-field semantics.
        state = {
            key: value
            for key, value in state.items()
            if key not in defaults or value != defaults[key]
        }
        super().__init__(**state)

    @classmethod
    def _settings_sources(
        cls,
        values: dict[str, Any],
        options: dict[str, Any],
        cli_source: Any,
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
        from .pydantic_settings_cli import CliSettingsSource

        if not any(isinstance(source, CliSettingsSource) for source in sources):
            if cli_source is not None:
                if options["cli_parse_args"] is not None:
                    cli_source(args=options["cli_parse_args"])
                sources = (cli_source, *sources)
            elif (
                options["cli_parse_args"] is not None
                and options["cli_parse_args"] is not False
            ):
                cli_options = {
                    key: value
                    for key, value in options.items()
                    if key.startswith("cli_")
                }
                if options["env_parse_none_str"] is not None:
                    cli_options["cli_parse_none_str"] = options["env_parse_none_str"]
                sources = (
                    CliSettingsSource[Any](
                        cls,
                        case_sensitive=options["case_sensitive"],
                        _env_settings_source=env,
                        **cli_options,
                    ),
                    *sources,
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
