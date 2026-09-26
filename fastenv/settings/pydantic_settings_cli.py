"""Command line settings built independently with argparse and Pydantic metadata."""

from __future__ import annotations

# BaseSettings imports the CLI only when requested, and CliApp imports it lazily.
# pyright: reportImportCycles=false
# Model fields and argparse adapters intentionally carry arbitrary validated values.
# pyright: reportAny=false, reportExplicitAny=false
import argparse
import asyncio
import inspect
import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace, UnionType
from typing import (
    Annotated,
    Any,
    Generic,
    Literal,
    TextIO,
    TypeVar,
    Union,  # pyright: ignore[reportDeprecated]
    cast,
    get_args,
    get_origin,
)

from pydantic import AliasChoices, AliasPath, BaseModel, Field, TypeAdapter
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined, to_jsonable_python

from .pydantic_settings_sources import (
    ForceDecode,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsError,
)

T = TypeVar("T")
BoolT = TypeVar("BoolT", bound=bool)
CLI_SUPPRESS = argparse.SUPPRESS
_active_help: ContextVar[CliSettingsSource[Any] | None] = ContextVar(
    "fastenv_cli_help", default=None
)


class _SubCommand:
    pass


class _PositionalArg:
    pass


class _ImplicitFlag:
    pass


class _ExplicitFlag:
    pass


class _DualFlag:
    pass


class _ToggleFlag:
    pass


class _UnknownArgs:
    pass


CliSubCommand = Annotated[T | None, _SubCommand]
CliPositionalArg = Annotated[T, _PositionalArg]
CliImplicitFlag = Annotated[BoolT, _ImplicitFlag]
CliExplicitFlag = Annotated[BoolT, _ExplicitFlag]
CliDualFlag = Annotated[BoolT, _DualFlag]
CliToggleFlag = Annotated[BoolT, _ToggleFlag]
CliSuppress = Annotated[T, CLI_SUPPRESS]
CliUnknownArgs = Annotated[
    list[str], Field(default_factory=list), _UnknownArgs, NoDecode
]


class CliMutuallyExclusiveGroup(BaseModel):
    """Group nested options so at most one may be supplied."""


def _fields(model: Any) -> dict[str, FieldInfo]:
    fields = getattr(model, "model_fields", None)
    if fields is None:
        fields = getattr(model, "__pydantic_fields__", None)
    if fields is None:
        raise SettingsError(
            "CLI models must be Pydantic models or Pydantic dataclasses"
        )
    return fields


def _types(annotation: Any) -> tuple[Any, ...]:
    if get_origin(annotation) is Annotated:
        return _types(get_args(annotation)[0])
    if get_origin(annotation) in (Union, UnionType):  # pyright: ignore[reportDeprecated]
        return tuple(t for item in get_args(annotation) for t in _types(item))
    return (annotation,)


def _models(annotation: Any) -> list[type[Any]]:
    return [
        t
        for t in _types(annotation)
        if isinstance(t, type)
        and (hasattr(t, "model_fields") or hasattr(t, "__pydantic_fields__"))
    ]


def _aliases(name: str, field: FieldInfo) -> list[str | AliasPath]:
    alias = field.validation_alias or field.alias
    if isinstance(alias, AliasChoices):
        return list(alias.choices)
    return [alias] if isinstance(alias, (str, AliasPath)) else [name]


def _path(name: str, field: FieldInfo) -> tuple[str | int, ...]:
    alias = _aliases(name, field)[0]
    return tuple(alias.path) if isinstance(alias, AliasPath) else (alias,)


def _put(target: dict[str, Any], path: tuple[str | int, ...], value: Any) -> None:
    current: Any = target
    for index, key in enumerate(path[:-1]):
        next_key = path[index + 1]
        if isinstance(current, list):
            current = cast(Any, current)
            while len(current) <= int(key):
                current.append(None)
            if current[int(key)] is None:
                current[int(key)] = [] if isinstance(next_key, int) else {}
            current = current[int(key)]
        else:
            if not isinstance(current.get(key), (dict, list)):
                current[key] = [] if isinstance(next_key, int) else {}
            current = current[key]
    key = path[-1]
    if isinstance(current, list):
        current = cast(Any, current)
        while len(current) <= int(key):
            current.append(None)
        current[int(key)] = value
    elif isinstance(value, dict) and isinstance(current.get(key), dict):
        current[key] = _merge(current[key], cast(dict[str, Any], value))
    else:
        current[key] = value


def _merge(lower: dict[str, Any], higher: dict[str, Any]) -> dict[str, Any]:
    result = dict(lower)
    for key, value in higher.items():
        result[key] = (
            _merge(result[key], cast(dict[str, Any], value))
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else value
        )
    return result


def _split(value: str) -> list[str]:
    """Split commas outside quoted strings and nested JSON containers."""
    result: list[str] = []
    start = depth = 0
    quote = ""
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\" and quote:
            escaped = True
        elif quote:
            if char == quote:
                quote = ""
        elif char in ('"', "'"):
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    result.append(value[start:].strip())
    return result


def _atom(value: str) -> Any:
    try:
        parsed = json.loads(value)
    except ValueError:
        return value
    # CLI numeric tokens are strings until Pydantic selects a field's type.
    # Values inside JSON objects or nested arrays retain their JSON types.
    return (
        value
        if isinstance(parsed, (int, float)) and not isinstance(parsed, bool)
        else parsed
    )


def _collection(annotation: Any) -> str | None:
    for member in _types(annotation):
        origin = get_origin(member) or member
        if isinstance(origin, type):
            if issubclass(origin, Mapping):
                return "dict"
            if issubclass(origin, (Sequence, set, frozenset)) and not issubclass(
                origin, (str, bytes, bytearray)
            ):
                return "list"
    return None


class _Parser(argparse.ArgumentParser):
    def __init__(
        self, *args: Any, cli_exit_on_error: bool = True, **kwargs: Any
    ) -> None:
        self.cli_exit_on_error: bool = cli_exit_on_error
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> Any:
        if self.cli_exit_on_error:
            return super().error(message)
        raise SettingsError(f"error parsing CLI: {message}")


@dataclass
class _Binding:
    dest: str
    path: tuple[str | int, ...]
    field: FieldInfo
    option: str
    positional: bool = False
    alias_container: Literal["list", "dict"] | None = None


class CliSettingsSource(PydanticBaseSettingsSource, Generic[T]):
    """Translate Pydantic fields into command line arguments and validation data.

    Parsing is optional at construction. Calling the source with ``args`` or
    ``parsed_args`` reloads it and returns the source. Calling it without either
    returns its current settings dictionary.
    """

    cli_prog_name: str | None
    cli_parse_args: bool | list[str] | tuple[str, ...] | None
    cli_parse_none_str: str
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
    cli_shortcuts: Mapping[str, str | list[str]]
    case_sensitive: bool

    def __init__(
        self,
        settings_cls: type[T],
        cli_prog_name: str | None = None,
        cli_parse_args: bool | list[str] | tuple[str, ...] | None = None,
        cli_parse_none_str: str | None = None,
        cli_hide_none_type: bool | None = None,
        cli_avoid_json: bool | None = None,
        cli_enforce_required: bool | None = None,
        cli_use_class_docs_for_groups: bool | None = None,
        cli_show_env_vars: bool | None = None,
        cli_exit_on_error: bool | None = None,
        cli_prefix: str | None = None,
        cli_flag_prefix_char: str | None = None,
        cli_implicit_flags: bool | Literal["dual", "toggle"] | None = None,
        cli_ignore_unknown_args: bool | None = None,
        cli_kebab_case: bool | Literal["all", "no_enums"] | None = None,
        cli_shortcuts: Mapping[str, str | list[str]] | None = None,
        case_sensitive: bool | None = True,
        root_parser: Any = None,
        parse_args_method: Callable[..., Any] | None = None,
        add_argument_method: Callable[..., Any]
        | None = argparse.ArgumentParser.add_argument,
        add_argument_group_method: Callable[..., Any]
        | None = argparse.ArgumentParser.add_argument_group,
        add_parser_method: Callable[..., Any]
        | None = argparse._SubParsersAction.add_parser,  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType]
        add_subparsers_method: Callable[..., Any]
        | None = argparse.ArgumentParser.add_subparsers,
        format_help_method: Callable[..., Any]
        | None = argparse.ArgumentParser.format_help,
        formatter_class: Any = argparse.RawDescriptionHelpFormatter,
        _env_settings_source: Any = None,
        _init_state: Any = None,
    ) -> None:
        super().__init__(
            settings_cls if issubclass(settings_cls, BaseModel) else BaseModel
        )
        self.settings_cls: type[Any] = settings_cls
        if not issubclass(settings_cls, BaseModel):
            self.config: dict[str, Any] = dict(
                getattr(settings_cls, "__pydantic_config__", {})
            )
        options = locals()
        defaults: dict[str, Any] = {
            "cli_prog_name": None,
            "cli_parse_args": None,
            "cli_parse_none_str": None,
            "cli_hide_none_type": False,
            "cli_avoid_json": False,
            "cli_enforce_required": False,
            "cli_use_class_docs_for_groups": False,
            "cli_show_env_vars": False,
            "cli_exit_on_error": True,
            "cli_prefix": "",
            "cli_flag_prefix_char": "-",
            "cli_implicit_flags": False,
            "cli_ignore_unknown_args": False,
            "cli_kebab_case": False,
            "cli_shortcuts": {},
            "case_sensitive": True,
        }
        for name, default in defaults.items():
            value = options[name]
            if value is None:
                value = self.config.get(name)
            setattr(self, name, default if value is None else value)
        self.cli_parse_none_str = (
            self.cli_parse_none_str
            or self.config.get("env_parse_none_str")
            or ("None" if self.cli_avoid_json else "null")
        )
        if not self.cli_flag_prefix_char or len(self.cli_flag_prefix_char) != 1:
            raise SettingsError("cli_flag_prefix_char must be a single character")
        if self.cli_prefix and (
            self.cli_prefix.startswith(".")
            or self.cli_prefix.endswith(".")
            or not all(part.isidentifier() for part in self.cli_prefix.split("."))
        ):
            raise SettingsError("cli_prefix must be a dot-separated identifier")
        self._methods: dict[str, Callable[..., Any] | None] = {
            "add_argument": add_argument_method,
            "add_argument_group": add_argument_group_method,
            "add_parser": add_parser_method,
            "add_subparsers": add_subparsers_method,
            "format_help": format_help_method,
        }
        self._parse_args_method: Callable[..., Any] | None = parse_args_method
        self._formatter_class: Any = formatter_class
        self.root_parser: Any = (
            root_parser
            if root_parser is not None
            else _Parser(
                prog=self.cli_prog_name,
                description=settings_cls.__doc__,
                prefix_chars=self.cli_flag_prefix_char,
                formatter_class=formatter_class,
                cli_exit_on_error=self.cli_exit_on_error,
                allow_abbrev=False,
            )
        )
        self._bindings: list[_Binding] = []
        self._env_settings_source: Any = _env_settings_source
        self._env_names_by_path: dict[tuple[str | int, ...], list[str]] = {}
        self._subcommands: list[tuple[str, tuple[str | int, ...]]] = []
        self._unknown_paths: list[tuple[str | int, ...]] = []
        self._data: dict[str, Any] = {}
        self._option_names: dict[str, str] = {}
        self._registered_options: dict[int, set[str]] = {}
        self._build(
            settings_cls,
            self.root_parser,
            (),
            self.cli_prefix + "." if self.cli_prefix else "",
            (),
        )
        if self.cli_parse_args is not None and self.cli_parse_args is not False:
            self(args=self.cli_parse_args)

    def _method(self, name: str, parser: Any, *args: Any, **kwargs: Any) -> Any:
        method = self._methods[name]
        if method is None:
            raise SettingsError(f"CLI parser requires {name}_method")
        return method(parser, *args, **kwargs)

    def _flag(self, name: str) -> str:
        name = name.replace("_", "-") if self.cli_kebab_case else name
        return self.cli_flag_prefix_char * (1 if len(name) == 1 else 2) + name

    def _env_option(self, name: str, default: Any = None) -> Any:
        return getattr(self._env_settings_source, name, self.config.get(name, default))

    def _help_env_names(
        self, model: type[Any], name: str, field: FieldInfo, path: tuple[str | int, ...]
    ) -> list[str]:
        aliases = _aliases(name, field)
        named = [
            (
                str(alias.path[0]) if isinstance(alias, AliasPath) else alias,
                bool(field.validation_alias or field.alias),
            )
            for alias in aliases
        ]
        config = getattr(model, "model_config", self.config)
        if (
            self.config.get("populate_by_name")
            or self.config.get("validate_by_name")
            or config.get("populate_by_name")
            or config.get("validate_by_name")
        ):
            named.append((name, False))
        prefix = self._env_option("env_prefix", "")
        target = self._env_option("env_prefix_target", "variable")
        if not path:
            names = [
                (
                    prefix
                    if target in ("all", "alias" if is_alias else "variable")
                    else ""
                )
                + alias
                for alias, is_alias in named
            ]
        else:
            delimiter = self._env_option("env_nested_delimiter")
            names = (
                [
                    parent + delimiter + alias
                    for parent in self._env_names_by_path.get(path, [])
                    for alias, _ in named
                ]
                if delimiter
                else []
            )
        if not self._env_option("case_sensitive", False):
            names = [value.upper() for value in names]
        return list(dict.fromkeys(names))

    def _build(
        self,
        model: type[Any],
        parser: Any,
        path: tuple[str | int, ...],
        prefix: str,
        ancestors: tuple[type[Any], ...],
    ) -> None:
        if model in ancestors:
            return
        subparser = None
        for name, field in _fields(model).items():
            field_path = path + _path(name, field)
            self._env_names_by_path[field_path] = self._help_env_names(
                model, name, field, path
            )
            aliases = _aliases(name, field)
            nested = _models(field.annotation)
            if _UnknownArgs in field.metadata:
                self._unknown_paths.append(field_path)
                continue
            if _SubCommand in field.metadata:
                if not field.is_required() or not nested:
                    raise SettingsError(
                        f"subcommand {name!r} must be a required Pydantic model field"
                    )
                if len(aliases) != 1:
                    raise SettingsError(f"subcommand {name!r} must have a single alias")
                if subparser is None:
                    subparser = self._method("add_subparsers", parser)
                for child in nested:
                    command = child.__name__ if len(nested) > 1 else str(aliases[0])
                    command = (
                        command.replace("_", "-") if self.cli_kebab_case else command
                    )
                    child_parser = self._method(
                        "add_parser",
                        subparser,
                        command,
                        help=inspect.cleandoc(child.__doc__ or ""),
                        formatter_class=self._formatter_class,
                    )
                    if isinstance(child_parser, _Parser):
                        child_parser.cli_exit_on_error = self.cli_exit_on_error
                    selector = "__fastenv_command_" + str(len(self._subcommands))
                    _ = child_parser.set_defaults(**{selector: True})
                    self._subcommands.append((selector, field_path))
                    self._build(
                        child, child_parser, field_path, "", ancestors + (model,)
                    )
                continue
            positional = _PositionalArg in field.metadata
            if positional and len(aliases) != 1:
                raise SettingsError(
                    f"positional argument {name!r} must have a single alias"
                )
            visible = prefix + str(
                aliases[0] if isinstance(aliases[0], str) else aliases[0].path[0]
            )
            if nested and not positional:
                if any(
                    issubclass(child, CliMutuallyExclusiveGroup) for child in nested
                ):
                    if len(nested) != 1 or any(
                        _models(f.annotation) for f in _fields(nested[0]).values()
                    ):
                        raise SettingsError(
                            "CLI mutually exclusive groups cannot contain nested models or unions"
                        )
                    group = parser.add_mutually_exclusive_group()
                else:
                    if not self.cli_avoid_json or any(
                        isinstance(alias, AliasPath) for alias in aliases
                    ):
                        self._add(
                            parser, field_path, field, aliases, prefix, positional=False
                        )
                    description = (
                        inspect.cleandoc(nested[0].__doc__ or "")
                        if self.cli_use_class_docs_for_groups
                        else field.description
                    )
                    group = self._method(
                        "add_argument_group",
                        parser,
                        visible + " options",
                        description=description,
                    )
                # Shared names in model unions are connected only once.
                for alias in aliases:
                    if isinstance(alias, str):
                        for child in nested:
                            self._build(
                                child,
                                group,
                                field_path,
                                prefix + alias + ".",
                                ancestors + (model,),
                            )
            else:
                self._add(parser, field_path, field, aliases, prefix, positional)

    def _add(
        self,
        parser: Any,
        path: tuple[str | int, ...],
        field: FieldInfo,
        aliases: list[str | AliasPath],
        prefix: str,
        positional: bool,
    ) -> None:
        normal_aliases = [alias for alias in aliases if isinstance(alias, str)]
        if normal_aliases:
            self._add_binding(
                parser,
                path,
                field,
                [prefix + alias for alias in normal_aliases],
                positional,
            )
        for alias in aliases:
            if isinstance(alias, AliasPath):
                container = prefix + str(alias.path[0])
                self._add_binding(
                    parser,
                    path[: -len(_path("", field))] + (alias.path[0],),
                    field,
                    [container],
                    False,
                    alias_container="list"
                    if len(alias.path) > 1 and isinstance(alias.path[1], int)
                    else "dict",
                )

    def _add_binding(
        self,
        parser: Any,
        path: tuple[str | int, ...],
        field: FieldInfo,
        names: list[str],
        positional: bool,
        alias_container: Literal["list", "dict"] | None = None,
    ) -> None:
        options = [self._flag(name) for name in names]
        shortcuts = self.cli_shortcuts.get(names[0], [])
        options += [
            self._flag(shortcut)
            for shortcut in ([shortcuts] if isinstance(shortcuts, str) else shortcuts)
        ]
        scope = id(getattr(parser, "_actions", parser))
        registered = self._registered_options.setdefault(scope, set())
        options = [
            option for option in dict.fromkeys(options) if option not in registered
        ]
        if not options:
            return
        dest = ".".join(str(part) for part in path)
        binding = _Binding(dest, path, field, options[0], positional, alias_container)
        self._bindings.append(binding)
        registered.update(options)
        self._option_names.update({option: option for option in options})
        help_text = (
            argparse.SUPPRESS
            if CLI_SUPPRESS in field.metadata or field.description == CLI_SUPPRESS
            else field.description or ""
        )
        if help_text != argparse.SUPPRESS:
            default = field.get_default(call_default_factory=False)
            suffix = (
                "required"
                if field.is_required()
                else f"default: {default}"
                if default is not PydanticUndefined
                else "default factory"
            )
            help_text = f"{help_text} ({suffix})".strip()
            if self.cli_show_env_vars:
                env_names = self._env_names_by_path.get(path, [])
                if env_names:
                    help_text += " [env: " + " | ".join(env_names) + "]"
        kwargs: dict[str, Any] = {"default": argparse.SUPPRESS, "help": help_text}
        if not positional:
            kwargs.update(
                dest=dest,
                required=bool(
                    self.cli_enforce_required
                    and field.is_required()
                    and not _models(field.annotation)
                ),
            )
        else:
            options = [dest]
            kwargs["metavar"] = names[0]
        flag_markers = {
            _ImplicitFlag,
            _ExplicitFlag,
            _DualFlag,
            _ToggleFlag,
        }.intersection(field.metadata)
        if flag_markers and field.annotation is not bool:
            raise SettingsError(f"CLI boolean flag {names[0]!r} must have type bool")
        implicit = (
            field.annotation is bool
            and _ExplicitFlag not in field.metadata
            and (bool(self.cli_implicit_flags) or bool(flag_markers))
            and not positional
        )
        if implicit:
            toggle = _ToggleFlag in field.metadata or (
                self.cli_implicit_flags == "toggle"
                and _DualFlag not in field.metadata
                and _ImplicitFlag not in field.metadata
            )
            if toggle and isinstance(field.default, bool):
                kwargs.update(action="store_const", const=not field.default)
                if field.default:
                    options = [
                        self.cli_flag_prefix_char * 2
                        + "no-"
                        + option.lstrip(self.cli_flag_prefix_char)
                        for option in options
                    ]
            elif self.cli_flag_prefix_char == "-":
                kwargs["action"] = argparse.BooleanOptionalAction
            else:
                kwargs.update(action="store_const", const=True)
                self._method(
                    "add_argument",
                    parser,
                    *[
                        self.cli_flag_prefix_char * 2
                        + "no-"
                        + option.lstrip(self.cli_flag_prefix_char)
                        for option in options
                    ],
                    dest=dest,
                    default=argparse.SUPPRESS,
                    action="store_const",
                    const=False,
                    help=argparse.SUPPRESS,
                )
        elif _collection(field.annotation) or alias_container:
            if positional:
                kwargs["nargs"] = "+" if field.is_required() else "*"
            else:
                kwargs["action"] = "append"
        elif positional and not field.is_required():
            kwargs["nargs"] = "?"
        if not implicit and "metavar" not in kwargs:
            labels: list[str] = []
            for member in _types(field.annotation):
                if member is type(None):
                    if not self.cli_hide_none_type:
                        labels.append(self.cli_parse_none_str)
                elif _models(member):
                    labels.append("JSON")
                elif isinstance(member, type) and issubclass(member, Enum):
                    labels.extend(member.__members__)
                elif get_origin(member) is Literal:
                    labels.extend(str(value) for value in get_args(member))
                else:
                    labels.append(
                        getattr(cast(Any, member), "__name__", str(cast(Any, member)))
                    )
            kwargs["metavar"] = (
                labels[0] if len(labels) == 1 else "{" + ",".join(labels) + "}"
            )
        action = self._method("add_argument", parser, *options, **kwargs)
        for option in getattr(action, "option_strings", []):
            self._option_names[option] = option
        self._option_names.update({option: option for option in options})

    def _decode(self, value: Any, binding: _Binding) -> Any:
        if not isinstance(value, (str, list)):
            return value
        if value == self.cli_parse_none_str:
            return None
        field = binding.field
        if NoDecode in field.metadata or (
            not self.config.get("enable_decoding", True)
            and ForceDecode not in field.metadata
        ):
            return (
                ",".join(cast(list[str], value)) if isinstance(value, list) else value
            )
        kind = binding.alias_container or _collection(field.annotation)
        if kind:
            values: list[Any] = (
                cast(list[Any], value) if isinstance(value, list) else [value]
            )
            if kind == "list":
                result: list[Any] = []
                for item in values:
                    if not isinstance(item, str):
                        result.append(item)
                    elif item.startswith("["):
                        _ = json.loads(item)
                        # Preserve the reference CLI's empty-list token behavior:
                        # [] supplies one empty string before field validation.
                        result.extend(_atom(piece) for piece in _split(item[1:-1]))
                    else:
                        result.extend(_atom(piece) for piece in _split(item))
                return result
            result_dict: dict[str, Any] = {}
            for item in values:
                if isinstance(item, dict):
                    result_dict.update(cast(dict[str, Any], item))
                elif item.startswith("{"):
                    result_dict.update(json.loads(item))
                else:
                    for piece in _split(item):
                        key, separator, entry = piece.partition("=")
                        if not separator:
                            raise ValueError("dictionary arguments must use key=value")
                        result_dict[key] = (
                            json.loads(entry) if entry.startswith('"') else entry
                        )
            return result_dict
        if isinstance(value, str):
            for member in _types(field.annotation):
                if isinstance(member, type) and issubclass(member, Enum):
                    token = (
                        value.replace("-", "_")
                        if self.cli_kebab_case == "all"
                        else value
                    )
                    if token in member.__members__:
                        return member[token]
            if _models(field.annotation):
                return json.loads(value)
        return cast(Any, value)

    def __call__(
        self,
        *,
        args: list[str] | tuple[str, ...] | bool | None = None,
        parsed_args: argparse.Namespace
        | SimpleNamespace
        | dict[str, Any]
        | None = None,
    ) -> Any:
        if args is None and parsed_args is None:
            return dict(self._data)
        if args is not None and parsed_args is not None:
            raise SettingsError("provide args or parsed_args, not both")
        unknown: list[str] = []
        if parsed_args is None:
            tokens = (
                sys.argv[1:]
                if args is True
                else []
                if args is False
                else list(args or [])
            )
            if not self.case_sensitive:
                lookup = {name.lower(): name for name in self._option_names}
                tokens = [
                    lookup.get(token.partition("=")[0].lower(), token.partition("=")[0])
                    + ("=" + token.partition("=")[2] if "=" in token else "")
                    if token.startswith(self.cli_flag_prefix_char)
                    else token
                    for token in tokens
                ]
            if self._parse_args_method is not None:
                parsed_args = self._parse_args_method(self.root_parser, tokens)
            elif self.cli_ignore_unknown_args:
                parsed_args, unknown = self.root_parser.parse_known_args(tokens)
            else:
                parsed_args = self.root_parser.parse_args(tokens)
        parsed = parsed_args if isinstance(parsed_args, dict) else vars(parsed_args)
        self._data = {}
        selected = {
            path for selector, path in self._subcommands if parsed.get(selector)
        }
        for path in sorted({path for _, path in self._subcommands}, key=len):
            if len(path) == 1 or path[:-1] in selected:
                _put(self._data, path, {} if path in selected else None)
        for binding in sorted(self._bindings, key=lambda item: len(item.path)):
            if binding.dest in parsed:
                try:
                    value = self._decode(parsed[binding.dest], binding)
                except (ValueError, TypeError) as exc:
                    raise SettingsError(
                        f"error parsing CLI value for {binding.option}: {exc}"
                    ) from exc
                _put(self._data, binding.path, value)
        for path in self._unknown_paths:
            if not self._subcommands or len(path) == 1 or path[:-1] in selected:
                _put(self._data, path, unknown)
        return self

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        key = _path(field_name, field)[0]
        return self._data.get(str(key)), str(key), False


def get_subcommand(
    model: Any,
    is_required: bool = True,
    cli_exit_on_error: bool | None = None,
    _suppress_errors: list[SettingsError | SystemExit] | None = None,
) -> Any:
    """Return the selected command or report a missing required command."""
    fields = _fields(type(model))
    names: list[str] = [
        name for name, field in fields.items() if _SubCommand in field.metadata
    ]
    for name in names:
        command = getattr(model, name, None)
        if command is not None:
            return command
    if is_required:
        message = "Error: CLI subcommand is required {" + ", ".join(names) + "}"
        config = getattr(cast(type[Any], type(model)), "model_config", {})
        should_exit = (
            config.get("cli_exit_on_error", True)
            if cli_exit_on_error is None
            else cli_exit_on_error
        )
        error = SystemExit(message) if should_exit else SettingsError(message)
        if _suppress_errors is not None:
            _suppress_errors.append(error)
        else:
            raise error
    return None


def _execute(
    model: Any,
    method_name: str,
    required: bool = False,
    source: CliSettingsSource[Any] | None = None,
) -> Any:
    method = getattr(model, method_name, None)
    if method is None:
        if required:
            raise SettingsError(
                f"CLI command {type(model).__name__} is missing {method_name}"
            )
        return model
    token = _active_help.set(source)
    try:
        result = method()
        if inspect.isawaitable(result):

            async def await_result() -> Any:
                return await result

            try:
                _ = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(await_result())
            else:
                context = copy_context()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(context.run, asyncio.run, await_result()).result()
    finally:
        _active_help.reset(token)
    return model


class CliApp:
    """Run Pydantic models as CLI applications and serialize their arguments."""

    @staticmethod
    def _source(model_cls: type[Any], **kwargs: Any) -> CliSettingsSource[Any]:
        from .pydantic_settings import BaseSettings

        if not issubclass(model_cls, BaseSettings):
            defaults: dict[str, Any] = {
                "case_sensitive": True,
                "cli_hide_none_type": True,
                "cli_avoid_json": True,
                "cli_enforce_required": True,
                "cli_implicit_flags": True,
                "cli_kebab_case": True,
            }
            defaults.update({k: v for k, v in kwargs.items() if v is not None})
            return CliSettingsSource(model_cls, **defaults)
        return CliSettingsSource(model_cls, **kwargs)

    @staticmethod
    def run(
        model_cls: type[T],
        cli_args: list[str]
        | argparse.Namespace
        | SimpleNamespace
        | dict[str, Any]
        | None = None,
        cli_settings_source: CliSettingsSource[Any] | None = None,
        cli_exit_on_error: bool | None = None,
        cli_show_env_vars: bool | None = None,
        cli_cmd_method_name: str = "cli_cmd",
        **model_init_data: Any,
    ) -> T:
        from .pydantic_settings import BaseSettings

        _ = _fields(model_cls)
        source = cli_settings_source or CliApp._source(
            model_cls,
            cli_exit_on_error=cli_exit_on_error,
            cli_show_env_vars=cli_show_env_vars,
            cli_parse_args=False,
        )
        if isinstance(cli_args, (argparse.Namespace, SimpleNamespace, dict)):
            source(parsed_args=cli_args)
        else:
            source(args=True if cli_args is None else cli_args)
        if issubclass(model_cls, BaseSettings):
            model = model_cls(_cli_settings_source=source, **model_init_data)
        else:
            defaults: dict[str, Any] = {}
            for name, field in _fields(model_cls).items():
                default = field.default
                if (
                    _models(field.annotation)
                    and default is not PydanticUndefined
                    and default is not None
                ):
                    _put(
                        defaults,
                        _path(name, field),
                        TypeAdapter[Any](cast(type[Any], type(default))).dump_python(
                            default, by_alias=True
                        ),
                    )
            data = _merge(_merge(defaults, model_init_data), source())
            model = TypeAdapter(model_cls).validate_python(data)
        return _execute(model, cli_cmd_method_name, source=source)

    @staticmethod
    def run_subcommand(
        model: T,
        cli_exit_on_error: bool | None = None,
        cli_show_env_vars: bool | None = None,
        cli_cmd_method_name: str = "cli_cmd",
    ) -> T:
        command = get_subcommand(model, cli_exit_on_error=cli_exit_on_error)
        source = CliApp._source(
            cast(type[Any], type(model)),
            cli_parse_args=False,
            cli_exit_on_error=cli_exit_on_error,
            cli_show_env_vars=cli_show_env_vars,
        )
        return _execute(command, cli_cmd_method_name, required=True, source=source)

    @staticmethod
    def format_help(
        model: Any,
        cli_settings_source: CliSettingsSource[Any] | None = None,
        strip_ansi_color: bool = False,
    ) -> str:
        model_cls = model if isinstance(model, type) else type(model)
        active = None if isinstance(model, type) else _active_help.get()
        source = (
            cli_settings_source
            or active
            or CliApp._source(model_cls, cli_parse_args=False)
        )
        result = source._method("format_help", source.root_parser)  # pyright: ignore[reportPrivateUsage]
        return re.sub(r"\x1b\[[0-9;]*m", "", result) if strip_ansi_color else result

    @staticmethod
    def print_help(
        model: Any,
        cli_settings_source: CliSettingsSource[Any] | None = None,
        file: TextIO | None = None,
        strip_ansi_color: bool = False,
    ) -> None:
        print(
            CliApp.format_help(model, cli_settings_source, strip_ansi_color),
            file=file or sys.stdout,
            end="",
        )

    @staticmethod
    def serialize(
        model: Any,
        list_style: Literal["json", "argparse", "lazy"] = "json",
        dict_style: Literal["json", "env"] = "json",
        positionals_first: bool = False,
    ) -> list[str]:
        if str(list_style) not in ("json", "argparse", "lazy") or str(
            dict_style
        ) not in (
            "json",
            "env",
        ):
            raise ValueError("invalid CLI collection serialization style")
        source = CliApp._source(cast(type[Any], type(model)), cli_parse_args=False)

        def render(value: Any) -> str:
            if isinstance(value, Enum):
                return (
                    value.name.replace("_", "-")
                    if source.cli_kebab_case == "all"
                    else value.name
                )
            if isinstance(value, str):
                return value
            if value is None:
                return source.cli_parse_none_str
            return json.dumps(to_jsonable_python(value))

        def visit(instance: Any, prefix: str = "") -> list[str]:
            named: list[str] = []
            positional: list[str] = []
            subcommands: list[str] = []
            aliased: dict[str, Any] = {}
            for name, field in _fields(type(instance)).items():
                value = getattr(instance, name)
                alias = _aliases(name, field)[0]
                alias_name = (
                    str(alias.path[0]) if isinstance(alias, AliasPath) else alias
                )
                if _SubCommand in field.metadata:
                    if value is not None:
                        command = (
                            type(value).__name__
                            if len(_models(field.annotation)) > 1
                            else alias_name
                        )
                        subcommands.append(
                            command.replace("_", "-")
                            if source.cli_kebab_case
                            else command
                        )
                        subcommands.extend(visit(value))
                    continue
                if _UnknownArgs in field.metadata:
                    named.extend(value)
                    continue
                if value == field.default:
                    continue
                if isinstance(alias, AliasPath):
                    _put(aliased, tuple(alias.path), to_jsonable_python(value))
                    continue
                if _PositionalArg in field.metadata:
                    positional.extend(
                        render(item) for item in cast(Iterable[Any], value)
                    ) if isinstance(value, (list, tuple)) else positional.append(
                        render(value)
                    )
                    continue
                option = source._flag(prefix + alias_name)  # pyright: ignore[reportPrivateUsage]
                if _models(field.annotation) and value is not None:
                    named.extend(visit(value, prefix + alias_name + "."))
                elif (
                    isinstance(value, bool)
                    and _ExplicitFlag not in field.metadata
                    and (
                        source.cli_implicit_flags
                        or any(
                            marker in field.metadata
                            for marker in (_ImplicitFlag, _DualFlag, _ToggleFlag)
                        )
                    )
                ):
                    named.append(
                        option
                        if value
                        else source.cli_flag_prefix_char * 2
                        + "no-"
                        + option.lstrip(source.cli_flag_prefix_char)
                    )
                elif (
                    isinstance(value, (list, tuple, set, frozenset))
                    and list_style != "json"
                ):
                    if list_style == "lazy":
                        named.extend(
                            [
                                option,
                                ",".join(
                                    render(item) for item in cast(Iterable[Any], value)
                                ),
                            ]
                        )
                    else:
                        for item in cast(Iterable[Any], value):
                            named.extend([option, render(item)])
                elif isinstance(value, dict) and dict_style == "env":
                    for key, item in cast(dict[str, Any], value).items():
                        named.extend([option, f"{key}={render(item)}"])
                else:
                    named.extend([option, render(value)])

            for name, value in aliased.items():
                option = source._flag(prefix + name)  # pyright: ignore[reportPrivateUsage]
                named.extend([option, json.dumps(value)])
            return (
                positional + named if positionals_first else named + positional
            ) + subcommands

        return visit(model, source.cli_prefix + "." if source.cli_prefix else "")
