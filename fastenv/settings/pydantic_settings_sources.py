"""Settings sources implemented with Pydantic's public model APIs and fastenv.

Each source returns validation inputs. Sources never modify the process environment.
"""

from __future__ import annotations

# Source hooks intentionally accept arbitrary Pydantic field values.
# pyright: reportAny=false, reportExplicitAny=false
import dataclasses
import json
import os
import types
import typing
import warnings
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import (
    Annotated,
    Any,
    cast,
    get_args,
    get_origin,
)

from pydantic import AliasChoices, AliasPath, BaseModel, Json
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from fastenv.dotenv import parse_dotenv


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


ENV_FILE_SENTINEL = Path("")


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

    def _option(self, name: str, value: Any, default: Any = None) -> Any:
        return self.config.get(name, default) if value is None else value

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

    def __call__(self) -> dict[str, Any]:
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
        self.env_vars: dict[str, Any] = self._load_env_vars()

    def _load_env_vars(self) -> dict[str, Any]:
        return self._parse_env_vars(os.environ)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        names = self._names(field_name, field)
        for env_name, path in names:
            value = self.env_vars.get(env_name)
            if value is not None:
                return value, str(path[0]), len(path) > 1
        return None, str(names[0][1][0]), False

    def _enum_value(self, value: Any, annotation: Any) -> Any:
        from enum import Enum

        if self.env_parse_enums and isinstance(value, str):
            if isinstance(annotation, type) and issubclass(annotation, Enum):
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
        env_file: Any = ENV_FILE_SENTINEL,
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
        config = settings_cls.model_config
        self.env_file: Any = (
            config.get("env_file") if env_file == ENV_FILE_SENTINEL else env_file
        )
        self.env_file_encoding: str | None = env_file_encoding or config.get(
            "env_file_encoding"
        )
        self.dotenv_filtering: str | None = dotenv_filtering or config.get(
            "dotenv_filtering"
        )
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

    def _read_env_file(self, file_path: Path) -> dict[str, Any]:
        contents = file_path.read_text(encoding=self.env_file_encoding)
        return self._parse_env_vars(parse_dotenv(contents, case_sensitive=True))

    def _read_env_files(self) -> dict[str, Any]:
        if self.env_file is None:
            return {}
        files = (
            [self.env_file]
            if isinstance(self.env_file, (str, os.PathLike))
            else self.env_file
        )
        result: dict[str, Any] = {}
        for file in files:
            path = Path(cast(str | os.PathLike[str], file)).expanduser()
            if path.is_file() or path.is_fifo():
                result.update(self._read_env_file(path))
        return result

    def _load_env_vars(self) -> dict[str, Any]:
        return self._read_env_files()

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
        self.secrets_paths: list[Path] = []

    @staticmethod
    def find_case_path(
        dir_path: Path, file_name: str, case_sensitive: bool
    ) -> Path | None:
        for path in dir_path.iterdir():
            if path.name == file_name or (
                not case_sensitive and path.name.lower() == file_name.lower()
            ):
                return path
        return None

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        names = self._names(field_name, field)
        for env_name, alias in names:
            for directory in reversed(self.secrets_paths):
                path = self.find_case_path(directory, env_name, self.case_sensitive)
                if path is None:
                    continue
                if not path.is_file():
                    warnings.warn(f'Secret path "{path}" is not a file', stacklevel=2)
                    continue
                value = path.read_text().strip()
                return value, str(alias[0]), len(alias) > 1
        return None, str(names[0][1][0]), False

    def __call__(self) -> dict[str, Any]:
        if self.secrets_dir is None:
            return {}
        directories = (
            [self.secrets_dir]
            if isinstance(self.secrets_dir, (str, os.PathLike))
            else self.secrets_dir
        )
        self.secrets_paths = []
        for directory in directories:
            path = Path(cast(str | os.PathLike[str], directory)).expanduser()
            if not path.exists():
                warnings.warn(f'directory "{path}" does not exist', stacklevel=2)
            elif not path.is_dir():
                raise SettingsError(
                    f'secrets_dir must reference a directory, not "{path}"'
                )
            else:
                self.secrets_paths.append(path)
        return super().__call__()
