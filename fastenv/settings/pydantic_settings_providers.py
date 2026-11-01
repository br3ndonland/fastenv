# Parsed configuration and user-supplied settings are dynamic at this boundary.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

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

import anyio
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .pydantic_settings_sources import (
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsError,
    configured_paths,
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


class _ConfigFileSettingsSource(PydanticBaseSettingsSource, ABC):
    """Merge configuration documents, reading them on each call or load."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        files: ConfigPaths,
        *,
        encoding: str | None = "utf-8",
        deep_merge: bool,
    ) -> None:
        super().__init__(settings_cls)
        self._files: ConfigPaths = files
        self._encoding: str | None = encoding
        self._deep_merge: bool = deep_merge
        self._preloaded: dict[str, Any] | None = None

    def _paths(self) -> Sequence[Path | Traversable]:
        return configured_paths(self._files)

    def _read_files(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for path in self._paths():
            if not path.is_file():
                continue
            values = self._decode_file(path.read_text(encoding=self._encoding))
            if not isinstance(values, dict):
                raise SettingsError(f"Configuration file {path} must contain a mapping")
            if self._deep_merge:
                _merge_data(data, cast(dict[str, Any], values))
            else:
                data.update(cast(dict[str, Any], values))
        return data

    @abstractmethod
    def _decode_file(self, contents: str) -> Any:
        """Decode one configuration document with the selected format parser."""

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, "", False

    def __call__(self) -> dict[str, Any]:
        """Read the documents, unless `load` already did, then return the merge."""
        preloaded = self._preloaded
        return self._read_files() if preloaded is None else preloaded

    async def load(self) -> dict[str, Any]:
        """Read the documents in a worker thread, then return the merge.

        Package resources only expose synchronous Traversable methods, so one
        thread reads filesystem paths and resources alike.
        """
        self._preloaded = await anyio.to_thread.run_sync(self._read_files)
        try:
            return self()
        finally:
            self._preloaded = None


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
        config = settings_cls.model_config
        self.json_file: ConfigPaths = (
            config.get("json_file") if json_file == _CONFIG_DEFAULT else json_file
        )
        self.json_file_encoding: str | None = json_file_encoding or config.get(
            "json_file_encoding"
        )
        super().__init__(
            settings_cls,
            self.json_file,
            encoding=self.json_file_encoding,
            deep_merge=deep_merge,
        )

    def _decode_file(self, contents: str) -> Any:
        return json.loads(contents)


class TomlConfigSettingsSource(_ConfigFileSettingsSource):
    """Load TOML documents or a selected table in each document."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        toml_file: ConfigPaths = _CONFIG_DEFAULT,
        toml_table_header: tuple[str, ...] | None = None,
        deep_merge: bool = False,
        _init_state: Any = None,
    ) -> None:
        config = settings_cls.model_config
        self.toml_file: ConfigPaths = (
            config.get("toml_file") if toml_file == _CONFIG_DEFAULT else toml_file
        )
        self.toml_table_header: tuple[str, ...] = (
            config.get("toml_table_header", ())
            if toml_table_header is None
            else toml_table_header
        )
        super().__init__(settings_cls, self.toml_file, deep_merge=deep_merge)

    def _decode_file(self, contents: str) -> Any:
        values: Any = tomllib.loads(contents)
        for component in self.toml_table_header:
            if not isinstance(values, dict):
                raise SettingsError("TOML table header must select a mapping")
            values = cast(dict[str, Any], values)[component]
        return values


class PyprojectTomlConfigSettingsSource(TomlConfigSettingsSource):
    """Find pyproject.toml at a bounded ancestor depth and read its settings table."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        toml_file: Path | None = None,
        _init_state: Any = None,
    ) -> None:
        config = settings_cls.model_config
        header = config.get(
            "pyproject_toml_table_header", ("tool", "pydantic-settings")
        )
        super().__init__(settings_cls, toml_file, header)
        self.pyproject_toml_depth: int = config.get("pyproject_toml_depth", 0)

    def _paths(self) -> Sequence[Path | Traversable]:
        """Use the given file, or the nearest pyproject.toml within the depth."""
        if self.toml_file is not None:
            return super()._paths()
        directory = Path.cwd()
        candidates = [
            parent / "pyproject.toml"
            for parent in (directory, *directory.parents)[
                : self.pyproject_toml_depth + 1
            ]
        ]
        return [path for path in candidates if path.is_file()][:1]

    def _decode_file(self, contents: str) -> Any:
        try:
            return super()._decode_file(contents)
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
        for path in cast(list[Path], configured_paths(self.secrets_dir)):
            if not path.exists():
                self._missing_directory(path)
                continue
            if not path.is_dir():
                raise SettingsError(f'Secrets path "{path}" is not a directory')
            total = 0
            for secret in sorted(path.rglob("*")):
                if not secret.is_file():
                    continue
                self._check_size(path, total + secret.stat().st_size)
                # Bound the read as well as checking stat, in case a file grows.
                with secret.open("rb") as stream:
                    contents = stream.read(self.secrets_dir_max_size - total + 1)
                total += len(contents)
                self._check_size(path, total)
                key = str(secret.relative_to(path))
                variables[key if self.case_sensitive else key.lower()] = (
                    contents.decode().strip()
                )
        return self._parse_env_vars(variables)

    def _missing_directory(self, path: Path) -> None:
        message = f'Secrets directory "{path}" does not exist'
        if self.secrets_dir_missing == "error":
            raise SettingsError(message)
        if self.secrets_dir_missing == "warn":
            warnings.warn(message, UserWarning, stacklevel=3)

    def _check_size(self, path: Path, total: int) -> None:
        if total > self.secrets_dir_max_size:
            raise SettingsError(f'Secrets directory "{path}" exceeds maximum size')
