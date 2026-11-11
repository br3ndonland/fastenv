# Source hooks intentionally accept arbitrary Pydantic field values.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import dataclasses
import enum
import json
import os
import tomllib
import types
import typing
import warnings
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Mapping, Sequence
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Annotated, Any, Literal, cast, get_args, get_origin

import anyio
from pydantic import AliasChoices, AliasPath, BaseModel, Json
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from fastenv.utilities import logger, parse_dotenv


class SettingsError(ValueError):
    """A settings source could not read or decode a value."""


class IncompleteFieldDefinitionWarning(UserWarning):
    """A settings field contains an unresolved forward reference."""


def _has_forward_reference(annotation: Any) -> bool:
    return isinstance(annotation, typing.ForwardRef) or any(
        _has_forward_reference(argument) for argument in get_args(annotation)
    )


def _warn_incomplete_field(name: str, field: FieldInfo) -> None:
    if _has_forward_reference(field.annotation):
        warnings.warn(
            f"Field '{name}' has an unresolved forward reference. "
            + "Call model_rebuild() after all referenced types have been defined.",
            IncompleteFieldDefinitionWarning,
            stacklevel=3,
        )


class NoDecode:
    """Annotated metadata that leaves an environment value for field validators."""


class ForceDecode:
    """Annotated metadata that enables JSON parsing when decoding is disabled."""


class EnvNoneType(str):
    """Distinguish an explicit environment null from an absent variable."""


ConfigPath = str | Path | Traversable
ConfigPaths = ConfigPath | Sequence[ConfigPath] | None
SecretPaths = str | Path | Sequence[str | Path] | None
# Stands for the file in the model configuration, because None disables the file.
DEFAULT_PATH = Path("")
SECRETS_DIR_MAX_SIZE = 16 * 1024 * 1024


def configured_paths(value: Any) -> list[Any]:
    """List one or more configured paths, expanding home directories.

    Package resources are kept as they are, since they are not filesystem paths.
    """
    if value is None:
        return []
    if isinstance(value, (str, os.PathLike)) or not isinstance(value, Sequence):
        value = [value]
    return [
        Path(cast(str | os.PathLike[str], item)).expanduser()
        if isinstance(item, (str, os.PathLike))
        else item
        for item in cast(Sequence[Any], value)
    ]


def deep_merge(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Merge mappings recursively, preferring values from ``overrides``."""
    merged = dict(base)
    for key, value in overrides.items():
        previous = merged.get(key)
        merged[key] = (
            deep_merge(
                cast(Mapping[str, Any], previous), cast(Mapping[str, Any], value)
            )
            if isinstance(previous, Mapping) and isinstance(value, Mapping)
            else value
        )
    return merged


def _field_paths(
    name: str, field: FieldInfo, config: Mapping[str, Any]
) -> list[tuple[str | int, ...]]:
    alias = field.validation_alias
    paths: list[tuple[str | int, ...]] = []
    if config.get("validate_by_alias", True):
        choices = alias.choices if isinstance(alias, AliasChoices) else [alias]
        for choice in choices:
            if isinstance(choice, str):
                paths.append((choice,))
            elif isinstance(choice, AliasPath):
                paths.append(tuple(choice.path))
    if not paths or config.get("populate_by_name") or config.get("validate_by_name"):
        paths.append((name,))
    return paths


def _read_path(value: Any, path: Sequence[str | int]) -> Any:
    for part in path:
        if isinstance(value, str):
            return PydanticUndefined
        try:
            value = value[part]
        except (KeyError, IndexError, TypeError):
            return PydanticUndefined
    return value


def _write_path(target: dict[str, Any], path: Sequence[str | int], value: Any) -> None:
    """Write a validation alias path, including list positions."""

    def assign(node: Any, position: int) -> Any:
        if position == len(path):
            return value
        part = path[position]
        if node is None:
            node = [] if isinstance(part, int) else {}
        if isinstance(node, (list, tuple)):
            if not isinstance(part, int):
                raise SettingsError("A list validation alias requires an integer index")
            items = list(cast(Sequence[Any], node))
            required_length = part + 1 if part >= 0 else -part
            while len(items) < required_length:
                items.append(None)
            items[part] = assign(items[part], position + 1)
            return tuple(items) if isinstance(node, tuple) else items
        mapping = dict(cast(Mapping[str | int, Any], node))
        mapping[part] = assign(mapping.get(part), position + 1)
        return mapping

    target.update(assign(target, 0))


def canonicalize_inputs(
    settings_cls: type[BaseModel], values: Mapping[str, Any]
) -> dict[str, Any]:
    """Align alternate validation aliases so source priority applies per field."""
    result = dict(values)
    selected: list[tuple[tuple[str | int, ...], Any]] = []
    preferred_counts = Counter(
        _field_paths(name, field, settings_cls.model_config)[0]
        for name, field in settings_cls.model_fields.items()
    )
    for name, field in settings_cls.model_fields.items():
        paths = _field_paths(name, field, settings_cls.model_config)
        for path in paths:
            value = _read_path(values, path)
            if value is not PydanticUndefined:
                preferred = paths[0]
                if preferred_counts[preferred] > 1 and (name,) in paths:
                    preferred = (name,)
                selected.append(
                    (preferred, _canonicalize_annotation(field.annotation, value))
                )
                for candidate in paths:
                    if isinstance(candidate[0], str):
                        result.pop(candidate[0], None)
                break
    for path, value in selected:
        root = str(path[0])
        if len(path) > 1 and root in values:
            result.setdefault(root, values[root])
        _write_path(result, path, value)
    return result


def _annotation_complex(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is Annotated:
        return _annotation_complex(get_args(annotation)[0])
    if origin in (typing.Union, types.UnionType):  # pyright: ignore[reportDeprecated]
        return any(_annotation_complex(item) for item in get_args(annotation))
    actual = origin or annotation
    if actual in (str, bytes, bytearray):
        return False
    if not isinstance(actual, type):
        return False
    actual = cast(type[Any], actual)
    return (
        issubclass(actual, (BaseModel, Mapping, Sequence, set, frozenset))
        or dataclasses.is_dataclass(actual)
        or hasattr(actual, "__required_keys__")
    )


def _union_annotation(annotation: Any) -> bool:
    return get_origin(annotation) in (typing.Union, types.UnionType)  # pyright: ignore[reportDeprecated]


def _model_annotations(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [
        model
        for argument in get_args(annotation)
        for model in _model_annotations(argument)
    ]


def _model_annotation(annotation: Any) -> type[BaseModel] | None:
    models = _model_annotations(annotation)
    return models[0] if models else None


def _canonicalize_annotation(annotation: Any, value: Any) -> Any:
    model = _model_annotation(annotation)
    if model is not None and isinstance(value, Mapping):
        return canonicalize_inputs(model, cast(Mapping[str, Any], value))
    return value


def _plain_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        result: dict[str, Any] = {}
        for name, field in type(value).model_fields.items():
            path = _field_paths(name, field, value.model_config)[0]
            _write_path(result, path, _plain_default(getattr(value, name)))
        return result
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


class PydanticBaseSettingsSource(ABC):
    """Base protocol for callable settings sources and their decoding hooks."""

    def __init__(self, settings_cls: type[BaseModel]) -> None:
        self.settings_cls: type[BaseModel] = settings_cls
        self.config: dict[str, Any] = dict(settings_cls.model_config)
        self._current_state: dict[str, Any] = {}
        self._settings_sources_data: dict[str, dict[str, Any]] = {}

    @property
    def current_state(self) -> dict[str, Any]:
        return self._current_state

    @property
    def settings_sources_data(self) -> dict[str, dict[str, Any]]:
        return self._settings_sources_data

    def _set_current_state(self, state: dict[str, Any]) -> None:
        self._current_state = state

    def _set_settings_sources_data(self, states: dict[str, dict[str, Any]]) -> None:
        self._settings_sources_data = states

    def field_is_complex(self, field: FieldInfo) -> bool:
        return not any(
            isinstance(item, Json)  # pyright: ignore[reportArgumentType]
            for item in field.metadata
        ) and _annotation_complex(field.annotation)

    @abstractmethod
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        """Return a value, its validation key, and whether it requires decoding."""

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        if value is not None and (value_is_complex or self.field_is_complex(field)):
            return self.decode_complex_value(field_name, field, value)
        return value

    def decode_complex_value(
        self, field_name: str, field: FieldInfo, value: Any
    ) -> Any:
        _ = field_name
        if NoDecode in field.metadata or (
            not self.config.get("enable_decoding", True)
            and ForceDecode not in field.metadata
        ):
            return value
        return (
            json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value
        )

    @abstractmethod
    def __call__(self) -> dict[str, Any]:
        """Read validation inputs from this source."""

    async def load(self) -> dict[str, Any]:
        """Return inputs, with file sources overriding this to await their I/O."""
        return self()


class DefaultSettingsSource(PydanticBaseSettingsSource):
    """Expose nested default objects only when partial default updates are enabled."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        nested_model_default_partial_update: bool | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self.nested_model_default_partial_update: bool = (
            self.config.get("nested_model_default_partial_update", False)
            if nested_model_default_partial_update is None
            else nested_model_default_partial_update
        )
        self.defaults: dict[str, Any] = {}
        if self.nested_model_default_partial_update:
            for name, field in settings_cls.model_fields.items():
                if isinstance(field.default, BaseModel) or dataclasses.is_dataclass(
                    field.default
                ):
                    path = _field_paths(name, field, self.config)[0]
                    _write_path(self.defaults, path, _plain_default(field.default))

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return self.defaults.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return dict(self.defaults)


class InitSettingsSource(PydanticBaseSettingsSource):
    """Read explicitly supplied model inputs without decoding their strings."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        init_kwargs: dict[str, Any],
        nested_model_default_partial_update: bool | None = None,
    ) -> None:
        super().__init__(settings_cls)
        for name, field in settings_cls.model_fields.items():
            _warn_incomplete_field(name, field)
        self.init_kwargs: dict[str, Any] = dict(init_kwargs)
        self.nested_model_default_partial_update: bool = (
            self.config.get("nested_model_default_partial_update", False)
            if nested_model_default_partial_update is None
            else nested_model_default_partial_update
        )

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return self().get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        values = dict(self.init_kwargs)
        if not self.config.get("case_sensitive", False):
            for name, field in self.settings_cls.model_fields.items():
                for path in _field_paths(name, field, self.config):
                    root = str(path[0])
                    matching = [
                        key for key in self.init_kwargs if key.lower() == root.lower()
                    ]
                    if matching:
                        for key in matching:
                            values.pop(key, None)
                        values[root] = self.init_kwargs[matching[0]]
        values = canonicalize_inputs(self.settings_cls, values)
        if self.nested_model_default_partial_update:
            return {key: _plain_default(value) for key, value in values.items()}
        return values


class PydanticBaseEnvSettingsSource(PydanticBaseSettingsSource, ABC):
    """Shared name matching, scalar parsing, and validation for text sources."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        case_sensitive: bool | None = None,
        env_prefix: str | None = None,
        env_prefix_target: str | None = None,
        env_ignore_empty: bool | None = None,
        env_parse_none_str: str | None = None,
        env_parse_enums: bool | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self.case_sensitive: bool = self._option(
            "case_sensitive", case_sensitive, False
        )
        self.env_prefix: str = self._option("env_prefix", env_prefix, "")
        self.env_ignore_empty: bool = self._option(
            "env_ignore_empty", env_ignore_empty, False
        )
        self.env_parse_none_str: str | None = self._option(
            "env_parse_none_str", env_parse_none_str
        )
        self.env_parse_enums: bool = self._option(
            "env_parse_enums", env_parse_enums, False
        )
        self.env_prefix_target: str = self._option(
            "env_prefix_target", env_prefix_target, "variable"
        )
        self.env_vars: dict[str, Any] = {}
        self._preloaded: dict[str, Any] | None = None

    @abstractmethod
    def _load_env_vars(self) -> dict[str, Any]:
        """Read this source's variables, keyed by matched name."""

    def _option(self, name: str, value: Any, default: Any = None) -> Any:
        """Prefer the argument, then the model config, then the default."""
        if value is None:
            value = self.config.get(name)
        return default if value is None else value

    def _case(self, name: str) -> str:
        return name if self.case_sensitive else name.lower()

    def _names(
        self, name: str, field: FieldInfo, *, normalize: bool = True
    ) -> list[tuple[str, tuple[str | int, ...]]]:
        paths = _field_paths(name, field, self.config)
        result: list[tuple[str, tuple[str | int, ...]]] = []
        for path in paths:
            is_alias = path != (name,) or field.validation_alias is not None
            if path == (name,) and path is not paths[0]:
                is_alias = False
            prefix = (
                self.env_prefix
                if self.env_prefix_target
                in ("all", "alias" if is_alias else "variable")
                else ""
            )
            env_name = prefix + str(path[0])
            result.append((self._case(env_name) if normalize else env_name, path))
        return result

    def _parse_env_vars(self, values: Mapping[str, str | None]) -> dict[str, Any]:
        return {
            self._case(key): EnvNoneType(value)
            if self.env_parse_none_str is not None and value == self.env_parse_none_str
            else value
            for key, value in values.items()
            if not (self.env_ignore_empty and value == "")
        }

    def _normalize_nested(self, value: Any, annotation: Any) -> Any:
        if isinstance(value, EnvNoneType):
            return None
        if isinstance(value, list):
            args = get_args(annotation)
            return [
                self._normalize_nested(item, args[0] if args else Any)
                for item in cast(list[Any], value)
            ]
        if not isinstance(value, dict):
            return value
        value = cast(dict[str, Any], value)
        models = _model_annotations(annotation)
        if not models:
            return {
                key: self._normalize_nested(item, Any) for key, item in value.items()
            }
        fields = [
            (name, field, model.model_config)
            for model in models
            for name, field in model.model_fields.items()
        ]
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            found = False
            for name, field, config in fields:
                paths = _field_paths(name, field, config)
                for path in paths:
                    if len(path) == 1 and self._case(str(path[0])) == self._case(key):
                        _write_path(
                            normalized,
                            paths[0],
                            self._normalize_nested(item, field.annotation),
                        )
                        found = True
                        break
                if found:
                    break
            if not found:
                normalized[key] = self._normalize_nested(item, Any)
        return normalized

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        names = self._names(field_name, field)
        for env_name, path in names:
            value = self.env_vars.get(env_name)
            if value is not None:
                return value, str(path[0]), len(path) > 1
        return None, str(names[0][1][0]), False

    def __call__(self) -> dict[str, Any]:
        """Read variables, unless `load` already did, then return field inputs."""
        preloaded = self._preloaded
        self.env_vars = self._load_env_vars() if preloaded is None else preloaded
        result: dict[str, Any] = {}
        for name, field in self.settings_cls.model_fields.items():
            _warn_incomplete_field(name, field)
            try:
                value, key, complex_value = self.get_field_value(field, name)
            except (OSError, ValueError) as error:
                raise SettingsError(
                    f'error getting value for field "{name}" from source "{type(self).__name__}"'
                ) from error
            try:
                value = self.prepare_field_value(name, field, value, complex_value)
            except (ValueError, TypeError) as error:
                raise SettingsError(
                    f'error parsing value for field "{name}" from source "{type(self).__name__}"'
                ) from error
            if value is not None:
                result[key] = self._normalize_nested(value, field.annotation)
        return canonicalize_inputs(self.settings_cls, result)

    async def load(self) -> dict[str, Any]:
        """Read variables in a worker thread, then return field inputs.

        The synchronous reader is the only reader because settings constructors
        also have to work inside a running event loop. `StarletteConfig` does the
        inverse, with a constructor that runs its async reader in a new loop.
        """
        self._preloaded = await anyio.to_thread.run_sync(self._load_env_vars)
        try:
            return self()
        finally:
            self._preloaded = None


class EnvSettingsSource(PydanticBaseEnvSettingsSource):
    """Read process variables, JSON objects, and delimiter-separated nested keys."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        case_sensitive: bool | None = None,
        env_prefix: str | None = None,
        env_prefix_target: str | None = None,
        env_nested_delimiter: str | None = None,
        env_nested_max_split: int | None = None,
        env_ignore_empty: bool | None = None,
        env_parse_none_str: str | None = None,
        env_parse_enums: bool | None = None,
    ) -> None:
        super().__init__(
            settings_cls,
            case_sensitive=case_sensitive,
            env_prefix=env_prefix,
            env_prefix_target=env_prefix_target,
            env_ignore_empty=env_ignore_empty,
            env_parse_none_str=env_parse_none_str,
            env_parse_enums=env_parse_enums,
        )
        self.env_nested_delimiter: str | None = self._option(
            "env_nested_delimiter", env_nested_delimiter
        )
        self.env_nested_max_split: int | None = self._option(
            "env_nested_max_split", env_nested_max_split
        )

    def _load_env_vars(self) -> dict[str, Any]:
        return self._parse_env_vars(os.environ)

    def _enum_value(self, value: Any, annotation: Any) -> Any:
        if self.env_parse_enums and isinstance(value, str):
            if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
                return annotation.__members__.get(value, value)
            for argument in get_args(annotation):
                parsed = self._enum_value(value, argument)
                if parsed is not value:
                    return parsed
        return value

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        if isinstance(value, EnvNoneType):
            return value
        value = self._enum_value(value, field.annotation)
        complex_field = value_is_complex or self.field_is_complex(field)
        if complex_field and value is not None:
            try:
                value = self.decode_complex_value(field_name, field, value)
            except ValueError:
                if not _union_annotation(field.annotation):
                    raise
        if complex_field:
            nested = self.explode_env_vars(field_name, field, self.env_vars)
            if nested:
                value = (
                    deep_merge(cast(Mapping[str, Any], value), nested)
                    if isinstance(value, Mapping)
                    else nested
                )
        return value

    def next_field(
        self, field: FieldInfo | Any, key: str, case_sensitive: bool | None = None
    ) -> FieldInfo | None:
        annotation = field.annotation if isinstance(field, FieldInfo) else field
        origin = get_origin(annotation)
        if _union_annotation(annotation):
            for option in get_args(annotation):
                match = self.next_field(option, key, case_sensitive)
                if match is not None:
                    return match
            return None
        if (
            origin is not None
            and isinstance(origin, type)
            and issubclass(origin, Mapping)
        ):
            arguments = get_args(annotation)
            return (
                FieldInfo.from_annotation(arguments[1]) if len(arguments) > 1 else None
            )
        model = _model_annotation(annotation)
        if model is None:
            return None
        sensitive = self.case_sensitive if case_sensitive is None else case_sensitive
        for name, nested_field in model.model_fields.items():
            for path in _field_paths(name, nested_field, model.model_config):
                actual = str(path[0])
                if actual == key or (not sensitive and actual.lower() == key.lower()):
                    return nested_field
        return None

    def explode_env_vars(
        self, field_name: str, field: FieldInfo, env_vars: Mapping[str, Any]
    ) -> dict[str, Any]:
        delimiter = self.env_nested_delimiter
        if not delimiter:
            return {}
        result: dict[str, Any] = {}
        for env_name, _ in reversed(self._names(field_name, field)):
            prefix = env_name + delimiter
            for key, value in env_vars.items():
                if not key.startswith(prefix) or value is None:
                    continue
                remainder = key[len(prefix) :]
                limit = self.env_nested_max_split
                parts = remainder.split(delimiter, limit - 1 if limit else -1)
                target: Any = result
                current: FieldInfo | None = field
                for index, part in enumerate(parts):
                    current = self.next_field(current, part) if current else None
                    if index < len(parts) - 1:
                        if not isinstance(target.get(part), dict):
                            target[part] = {}
                        target = target[part]
                        continue
                    if current is not None:
                        value = self._enum_value(value, current.annotation)
                        if self.field_is_complex(current) and not isinstance(
                            value, EnvNoneType
                        ):
                            try:
                                value = self.decode_complex_value(part, current, value)
                            except ValueError:
                                if not _union_annotation(current.annotation):
                                    raise
                    elif field.annotation is dict and not isinstance(
                        value, EnvNoneType
                    ):
                        try:
                            value = json.loads(value)
                        except (ValueError, TypeError):
                            pass
                    target[part] = value
        return result


class DotEnvSettingsSource(EnvSettingsSource):
    """Read dotenv files with fastenv's parser without exporting their variables."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        env_file: Any = DEFAULT_PATH,
        env_file_encoding: str | None = None,
        dotenv_filtering: str | None = None,
        case_sensitive: bool | None = None,
        env_prefix: str | None = None,
        env_prefix_target: str | None = None,
        env_nested_delimiter: str | None = None,
        env_nested_max_split: int | None = None,
        env_ignore_empty: bool | None = None,
        env_parse_none_str: str | None = None,
        env_parse_enums: bool | None = None,
    ) -> None:
        super().__init__(
            settings_cls,
            case_sensitive=case_sensitive,
            env_prefix=env_prefix,
            env_prefix_target=env_prefix_target,
            env_nested_delimiter=env_nested_delimiter,
            env_nested_max_split=env_nested_max_split,
            env_ignore_empty=env_ignore_empty,
            env_parse_none_str=env_parse_none_str,
            env_parse_enums=env_parse_enums,
        )
        self.env_file: Any = (
            self.config.get("env_file") if env_file == DEFAULT_PATH else env_file
        )
        self.env_file_encoding: str | None = self._option(
            "env_file_encoding", env_file_encoding
        )
        self.dotenv_filtering: str | None = self._option(
            "dotenv_filtering", dotenv_filtering
        )

    def _load_env_vars(self) -> dict[str, Any]:
        env_vars: dict[str, Any] = {}
        for path in configured_paths(self.env_file):
            if path.is_file() or path.is_fifo():
                contents = path.read_text(encoding=self.env_file_encoding or "utf-8")
                variables = dict(parse_dotenv(contents, case_sensitive=True))
                logger.info(f"fastenv loaded {len(variables)} variables from {path}")
                env_vars.update(self._parse_env_vars(variables))
        return env_vars

    def __call__(self) -> dict[str, Any]:
        result = super().__call__()
        if self.dotenv_filtering == "only_existing":
            return result
        known: set[str] = set()
        prefixes: list[str] = []
        for name, field in self.settings_cls.model_fields.items():
            known.add(self._case(name))
            for env_name, _ in self._names(name, field):
                known.add(env_name)
                if self.env_nested_delimiter:
                    prefixes.append(env_name + self.env_nested_delimiter)
        prefix = self._case(self.env_prefix)
        for key, value in self.env_vars.items():
            if key in known or any(key.startswith(item) for item in prefixes):
                continue
            if self.dotenv_filtering == "match_prefix" and not key.startswith(prefix):
                continue
            output_key = key
            if (
                self.dotenv_filtering == "match_prefix"
                and prefix
                and key.startswith(prefix)
            ):
                output_key = key[len(prefix) :]
            result[output_key] = None if isinstance(value, EnvNoneType) else value
        return result


class SecretsSettingsSource(PydanticBaseEnvSettingsSource):
    """Load fields from individually named files in one or more directories."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        secrets_dir: Any = None,
        case_sensitive: bool | None = None,
        env_prefix: str | None = None,
        env_prefix_target: str | None = None,
        env_ignore_empty: bool | None = None,
        env_parse_none_str: str | None = None,
        env_parse_enums: bool | None = None,
    ) -> None:
        super().__init__(
            settings_cls,
            case_sensitive=case_sensitive,
            env_prefix=env_prefix,
            env_ignore_empty=env_ignore_empty,
            env_parse_none_str=env_parse_none_str,
            env_parse_enums=env_parse_enums,
            env_prefix_target=env_prefix_target,
        )
        self.secrets_dir: Any = (
            self.config.get("secrets_dir") if secrets_dir is None else secrets_dir
        )

    def _load_env_vars(self) -> dict[str, Any]:
        """Read the files named after fields, with later directories taking priority."""
        names = {
            env_name
            for name, field in self.settings_cls.model_fields.items()
            for env_name, _ in self._names(name, field)
        }
        secrets: dict[str, Any] = {}
        for directory in configured_paths(self.secrets_dir):
            if not directory.exists():
                warnings.warn(f'directory "{directory}" does not exist', stacklevel=2)
                continue
            if not directory.is_dir():
                raise SettingsError(
                    f'secrets_dir must reference a directory, not "{directory}"'
                )
            for path in directory.iterdir():
                if self._case(path.name) not in names:
                    continue
                if not path.is_file():
                    warnings.warn(f'Secret path "{path}" is not a file', stacklevel=2)
                    continue
                contents = path.read_text(encoding="utf-8")
                secrets[self._case(path.name)] = contents.strip()
        return secrets


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
        if secrets_dir is None:
            secrets_dir = getattr(wrapped, "secrets_dir", None)
        if case_sensitive is None:
            case_sensitive = getattr(wrapped, "case_sensitive", None)
        if env_prefix is None:
            env_prefix = getattr(wrapped, "env_prefix", None)
        super().__init__(
            settings_cls, case_sensitive=case_sensitive, env_prefix=env_prefix
        )
        self.case_sensitive: bool = self._option(
            "secrets_case_sensitive", secrets_case_sensitive, self.case_sensitive
        )
        self.env_prefix: str = self._option(
            "secrets_prefix", secrets_prefix, self.env_prefix
        )
        self.secrets_dir: SecretPaths = self._option("secrets_dir", secrets_dir)
        self.secrets_dir_missing: str = self._option(
            "secrets_dir_missing", secrets_dir_missing, "warn"
        )
        if self.secrets_dir_missing not in ("ok", "warn", "error"):
            raise SettingsError("secrets_dir_missing must be 'ok', 'warn', or 'error'")
        self.secrets_dir_max_size: int = self._option(
            "secrets_dir_max_size", secrets_dir_max_size, SECRETS_DIR_MAX_SIZE
        )
        self.secrets_nested_subdir: bool = self._option(
            "secrets_nested_subdir", secrets_nested_subdir, False
        )
        delimiter = self._option("secrets_nested_delimiter", secrets_nested_delimiter)
        if self.secrets_nested_subdir:
            if delimiter is not None:
                raise SettingsError(
                    "secrets_nested_subdir and secrets_nested_delimiter are mutually exclusive"
                )
            delimiter = os.sep
        self.env_nested_delimiter: str | None = self._option(
            "env_nested_delimiter", delimiter
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


class _ConfigFileSettingsSource(PydanticBaseSettingsSource, ABC):
    """Merge configuration documents, reading them on each call or load."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        files: ConfigPaths,
        *,
        encoding: str = "utf-8",
        deep_merge: bool,
    ) -> None:
        super().__init__(settings_cls)
        self._files: ConfigPaths = files
        self._encoding: str = encoding
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
            values = cast(dict[str, Any], values)
            logger.info(f"fastenv loaded {len(values)} variables from {path}")
            if self._deep_merge:
                data = deep_merge(data, values)
            else:
                data.update(values)
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
        json_file: ConfigPaths = DEFAULT_PATH,
        json_file_encoding: str | None = None,
        deep_merge: bool = False,
        _init_state: Any = None,
    ) -> None:
        config = settings_cls.model_config
        self.json_file: ConfigPaths = (
            config.get("json_file") if json_file == DEFAULT_PATH else json_file
        )
        self.json_file_encoding: str | None = json_file_encoding or config.get(
            "json_file_encoding"
        )
        super().__init__(
            settings_cls,
            self.json_file,
            encoding=self.json_file_encoding or "utf-8",
            deep_merge=deep_merge,
        )

    def _decode_file(self, contents: str) -> Any:
        return json.loads(contents)


class TomlConfigSettingsSource(_ConfigFileSettingsSource):
    """Load TOML documents or a selected table in each document."""

    def __init__(
        self,
        settings_cls: type[BaseModel],
        toml_file: ConfigPaths = DEFAULT_PATH,
        toml_table_header: tuple[str, ...] | None = None,
        deep_merge: bool = False,
        _init_state: Any = None,
    ) -> None:
        config = settings_cls.model_config
        self.toml_file: ConfigPaths = (
            config.get("toml_file") if toml_file == DEFAULT_PATH else toml_file
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
