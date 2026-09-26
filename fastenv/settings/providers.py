"""Optional settings sources for local configuration files and secret directories."""

# Parsed configuration and user-supplied settings are dynamic at this boundary.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import importlib
import json
import os
import tomllib
import warnings
from abc import ABC, abstractmethod
from collections.abc import Sequence
from copy import deepcopy
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .sources import (
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsError,
)

ConfigPath = str | Path | Traversable
ConfigPaths = ConfigPath | Sequence[ConfigPath] | None
SecretPaths = str | Path | Sequence[str | Path] | None
_CONFIG_DEFAULT = Path("")
SECRETS_DIR_MAX_SIZE = 16 * 1024 * 1024


def _merge_data(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_data(target[key], cast(dict[str, Any], value))
        else:
            target[key] = deepcopy(cast(Any, value))


def _optional_module(name: str, extra: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ImportError(
            f"Install fastenv[{extra}] to use this settings source."
        ) from exc


class _ConfigFileSettingsSource(PydanticBaseSettingsSource, ABC):
    def __init__(self, settings_cls: type[BaseModel]) -> None:
        super().__init__(settings_cls)
        self.data: dict[str, Any] = {}

    def _load_files(self, files: ConfigPaths, *, deep_merge: bool = False) -> None:
        if files is None:
            return
        paths = [files] if isinstance(files, (str, Path, Traversable)) else files
        for item in paths:
            path = Path(item).expanduser() if isinstance(item, (str, Path)) else item
            if not path.is_file():
                continue
            values: Any = self._read_file(path)
            if not isinstance(values, dict):
                raise SettingsError(f"Configuration file {path} must contain a mapping")
            if deep_merge:
                _merge_data(self.data, cast(dict[str, Any], values))
            else:
                self.data.update(cast(dict[str, Any], values))

    @abstractmethod
    def _read_file(self, path: Path | Traversable) -> Any:
        """Read one configuration document with the selected format parser."""

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, "", False

    def __call__(self) -> dict[str, Any]:
        return deepcopy(self.data)


class JsonConfigSettingsSource(_ConfigFileSettingsSource):
    """Load JSON objects, with later files taking priority."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        json_file: ConfigPaths = _CONFIG_DEFAULT,
        json_file_encoding: str | None = None,
        deep_merge: bool = False,
        _init_state: Any = None,
    ) -> None:
        super().__init__(settings_cls)
        self.json_file: ConfigPaths = (
            self.config.get("json_file") if json_file == _CONFIG_DEFAULT else json_file
        )
        self.json_file_encoding: str | None = json_file_encoding or self.config.get(
            "json_file_encoding"
        )
        self._load_files(self.json_file, deep_merge=deep_merge)

    def _read_file(self, path: Path | Traversable) -> Any:
        return json.loads(path.read_text(encoding=self.json_file_encoding))


class TomlConfigSettingsSource(_ConfigFileSettingsSource):
    """Load TOML documents or a selected table in each document."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        toml_file: ConfigPaths = _CONFIG_DEFAULT,
        toml_table_header: tuple[str, ...] = (),
        deep_merge: bool = False,
        _init_state: Any = None,
    ) -> None:
        super().__init__(settings_cls)
        self.toml_file: ConfigPaths = (
            self.config.get("toml_file") if toml_file == _CONFIG_DEFAULT else toml_file
        )
        self.toml_table_header: tuple[str, ...] = toml_table_header or self.config.get(
            "toml_table_header", ()
        )
        self._load_files(self.toml_file, deep_merge=deep_merge)

    def _read_file(self, path: Path | Traversable) -> Any:
        values: Any = tomllib.loads(path.read_text(encoding="utf-8"))
        for component in self.toml_table_header:
            if not isinstance(values, dict):
                raise SettingsError("TOML table header must select a mapping")
            values = cast(dict[str, Any], values)[component]
        return values


class YamlConfigSettingsSource(_ConfigFileSettingsSource):
    """Read YAML with PyYAML's safe loader, optionally selecting a section."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        yaml_file: ConfigPaths = _CONFIG_DEFAULT,
        yaml_file_encoding: str | None = None,
        yaml_config_section: str | None = None,
        deep_merge: bool = False,
        _init_state: Any = None,
    ) -> None:
        super().__init__(settings_cls)
        self.yaml_file: ConfigPaths = (
            self.config.get("yaml_file") if yaml_file == _CONFIG_DEFAULT else yaml_file
        )
        self.yaml_file_encoding: str | None = yaml_file_encoding or self.config.get(
            "yaml_file_encoding"
        )
        self.yaml_config_section: str | None = (
            yaml_config_section
            if yaml_config_section is not None
            else self.config.get("yaml_config_section")
        )
        self._load_files(self.yaml_file, deep_merge=deep_merge)

    def _read_file(self, path: Path | Traversable) -> Any:
        yaml = _optional_module("yaml", "yaml")
        values: Any = (
            yaml.safe_load(path.read_text(encoding=self.yaml_file_encoding)) or {}
        )
        if self.yaml_config_section is not None:
            remaining = self.yaml_config_section
            while True:
                if not remaining:
                    raise ValueError("yaml_config_section cannot be empty")
                if not isinstance(values, dict):
                    raise TypeError("YAML section path must traverse a mapping")
                section = cast(dict[str, Any], values)
                if remaining in section:
                    values = section[remaining]
                    break
                component, separator, remaining = remaining.partition(".")
                if not separator or component not in section:
                    raise KeyError(self.yaml_config_section)
                values = section[component]
            if not isinstance(values, dict):
                raise TypeError("YAML section must contain a mapping")
        return cast(Any, values)


class PyprojectTomlConfigSettingsSource(TomlConfigSettingsSource):
    """Find pyproject.toml at a bounded ancestor depth and read its settings table."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        toml_file: Path | None = None,
        _init_state: Any = None,
    ) -> None:
        config: dict[str, Any] = dict(settings_cls.model_config)
        if toml_file is None:
            directory = Path.cwd()
            toml_file = directory / "pyproject.toml"
            for _ in range(max(0, config.get("pyproject_toml_depth", 0)) + 1):
                candidate = directory / "pyproject.toml"
                if candidate.is_file():
                    toml_file = candidate
                    break
                directory = directory.parent
        header = config.get(
            "pyproject_toml_table_header", ("tool", "pydantic-settings")
        )
        # Initialize directly so an empty pyproject header selects the document root.
        _ConfigFileSettingsSource.__init__(self, settings_cls)
        self.toml_file: ConfigPaths = toml_file
        self.toml_table_header: tuple[str, ...] = header
        self._load_files(toml_file)

    def _read_file(self, path: Path | Traversable) -> Any:
        try:
            return super()._read_file(path)
        except KeyError:
            # An unrelated project's metadata need not contain a settings table.
            return {}


class NestedSecretsSettingsSource(EnvSettingsSource):
    """Read secret files as environment-shaped names, including nested paths."""

    def __init__(
        self,
        file_secret_settings: PydanticBaseSettingsSource | type[BaseModel],
        secrets_dir: SecretPaths = None,
        secrets_dir_missing: Literal["ok", "warn", "error"] | None = None,
        secrets_dir_max_size: int | None = None,
        secrets_case_sensitive: bool | None = None,
        secrets_prefix: str | None = None,
        secrets_nested_delimiter: str | None = None,
        secrets_nested_subdir: bool | None = None,
        case_sensitive: bool | None = None,
        env_prefix: str | None = None,
        _init_state: Any = None,
    ) -> None:
        if isinstance(file_secret_settings, PydanticBaseSettingsSource):
            wrapped = file_secret_settings
            settings_cls = wrapped.settings_cls
        else:
            wrapped = None
            settings_cls = file_secret_settings
        config: dict[str, Any] = dict(settings_cls.model_config)
        self.secrets_dir: SecretPaths = (
            secrets_dir
            if secrets_dir is not None
            else getattr(wrapped, "secrets_dir", config.get("secrets_dir"))
        )
        self.secrets_dir_missing: str = secrets_dir_missing or config.get(
            "secrets_dir_missing", "warn"
        )
        if self.secrets_dir_missing not in ("ok", "warn", "error"):
            raise SettingsError("secrets_dir_missing must be 'ok', 'warn', or 'error'")
        self.secrets_dir_max_size: int = (
            secrets_dir_max_size
            if secrets_dir_max_size is not None
            else config.get("secrets_dir_max_size", SECRETS_DIR_MAX_SIZE)
        )
        self.secrets_nested_subdir: bool = (
            secrets_nested_subdir
            if secrets_nested_subdir is not None
            else config.get("secrets_nested_subdir", False)
        )
        delimiter = (
            secrets_nested_delimiter
            if secrets_nested_delimiter is not None
            else config.get("secrets_nested_delimiter")
        )
        if self.secrets_nested_subdir:
            if delimiter is not None:
                raise SettingsError(
                    "secrets_nested_subdir and secrets_nested_delimiter are mutually exclusive"
                )
            delimiter = os.sep
        elif delimiter is None:
            delimiter = config.get("env_nested_delimiter")
        sensitive = secrets_case_sensitive
        if sensitive is None:
            sensitive = config.get("secrets_case_sensitive")
        if sensitive is None:
            sensitive = (
                case_sensitive
                if case_sensitive is not None
                else getattr(wrapped, "case_sensitive", config.get("case_sensitive"))
            )
        prefix = secrets_prefix
        if prefix is None:
            prefix = config.get("secrets_prefix")
        if prefix is None:
            prefix = (
                env_prefix
                if env_prefix is not None
                else getattr(wrapped, "env_prefix", config.get("env_prefix"))
            )
        super().__init__(
            settings_cls,
            case_sensitive=sensitive,
            env_prefix=prefix,
            env_nested_delimiter=delimiter,
        )

    def _load_env_vars(self) -> dict[str, Any]:
        variables: dict[str, str] = {}
        directories = self.secrets_dir
        if directories is None:
            return variables
        paths = [directories] if isinstance(directories, (str, Path)) else directories
        for directory in paths:
            path = Path(directory).expanduser()
            if not path.exists():
                message = f'Secrets directory "{path}" does not exist'
                if self.secrets_dir_missing == "error":
                    raise SettingsError(message)
                if self.secrets_dir_missing == "warn":
                    warnings.warn(message, UserWarning, stacklevel=3)
                continue
            if not path.is_dir():
                raise SettingsError(f'Secrets path "{path}" is not a directory')
            total = 0
            for secret in sorted(path.rglob("*")):
                if not secret.is_file():
                    continue
                size = secret.stat().st_size
                total += size
                if total > self.secrets_dir_max_size:
                    raise SettingsError(
                        f'Secrets directory "{path}" exceeds maximum size'
                    )
                # Bound the read as well as checking stat, in case a file grows.
                with secret.open("rb") as stream:
                    contents = stream.read(self.secrets_dir_max_size - total + size + 1)
                if total - size + len(contents) > self.secrets_dir_max_size:
                    raise SettingsError(
                        f'Secrets directory "{path}" exceeds maximum size'
                    )
                key = str(secret.relative_to(path))
                variables[key if self.case_sensitive else key.lower()] = (
                    contents.decode().strip()
                )
        return self._parse_env_vars(variables)
