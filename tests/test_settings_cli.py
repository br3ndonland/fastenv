"""CLI contract tests using independently designed models and inputs."""


# Dynamic settings values have types determined by each test model.
# pyright: reportAny=false, reportExplicitAny=false

import argparse
import asyncio
from enum import Enum
from io import StringIO
from types import SimpleNamespace
from typing import Annotated, Any, ClassVar, Literal, TypeVar

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field, ValidationError
from pydantic.dataclasses import dataclass

from fastenv.settings.cli import (
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
from fastenv.settings.main import BaseSettings, SettingsConfigDict
from fastenv.settings.sources import NoDecode, SettingsError

SettingsT = TypeVar("SettingsT", bound=BaseSettings)


def _settings(model: type[SettingsT], **values: Any) -> SettingsT:
    """Call the dynamic settings initializer without Pydantic's synthesized signature."""
    return model(**values)


def test_cli_priority_and_nested_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class Endpoint(BaseModel):
        hostname: str
        port: int = 5000

    class Settings(BaseSettings):
        endpoint: Endpoint
        retries: int = 0

    monkeypatch.setenv("RETRIES", "3")
    result = _settings(
        Settings,
        retries=5,
        _cli_parse_args=[
            "--retries",
            "8",
            "--endpoint.port",
            "8443",
            "--endpoint",
            '{"hostname":"example.test","port":443}',
        ],
    )
    assert result.retries == 8
    assert result.endpoint == Endpoint(hostname="example.test", port=8443)


@pytest.mark.parametrize(
    "values",
    [
        ["--ports", "[80,443]"],
        ["--ports", "80", "--ports", "443"],
        ["--ports", "80,443"],
        ["--ports", "[80]", "--ports", "443"],
    ],
)
def test_cli_collection_styles(values: list[str]) -> None:
    class Settings(BaseSettings):
        ports: list[int]

    assert _settings(Settings, _cli_parse_args=values).ports == [80, 443]


def test_cli_dicts_and_quoted_commas() -> None:
    class Settings(BaseSettings):
        labels: dict[str, str]
        words: list[str]

    result = _settings(
        Settings,
        _cli_parse_args=[
            "--labels",
            'owner="ops,team",region=west',
            "--labels",
            '{"region":"east"}',
            "--words",
            '"hello, world",plain',
        ],
    )
    assert result.labels == {"owner": "ops,team", "region": "east"}
    assert result.words == ["hello, world", "plain"]


def test_cli_aliases_and_paths() -> None:
    class Settings(BaseSettings):
        host: str = Field(
            validation_alias=AliasChoices("n", "hostname", AliasPath("pair", 0))
        )
        port: int = Field(
            validation_alias=AliasChoices("p", "port", AliasPath("pair", 1))
        )

    assert (
        _settings(Settings, _cli_parse_args=["-n", "localhost", "-p", "9876"]).port
        == 9876
    )
    result = _settings(Settings, _cli_parse_args=["--pair", "localhost,9876"])
    assert result.host == "localhost"
    assert result.port == 9876


def test_cli_boolean_modes() -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_implicit_flags="toggle"
        )
        enabled: bool = True
        debug: CliDualFlag[bool] = False
        trace: CliToggleFlag[bool] = False
        cache: CliExplicitFlag[bool] = True
        quiet: CliImplicitFlag[bool] = False

    result = _settings(
        Settings,
        _cli_parse_args=[
            "--no-enabled",
            "--debug",
            "--trace",
            "--cache=false",
            "--quiet",
        ],
    )
    assert result.model_dump() == {
        "enabled": False,
        "debug": True,
        "trace": True,
        "cache": False,
        "quiet": True,
    }
    with pytest.raises(SettingsError, match="unrecognized"):
        _ = _settings(Settings, _cli_parse_args=["--enabled"], _cli_exit_on_error=False)


def test_cli_config_prefix_shortcuts_case_and_none() -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_prefix="service",
            cli_kebab_case=True,
            cli_shortcuts={"service.listen_port": "p"},
            cli_parse_none_str="unset",
        )
        listen_port: int | None = 80

    assert (
        _settings(
            Settings, _cli_parse_args=["--service.listen-port", "unset"]
        ).listen_port
        is None
    )
    assert _settings(Settings, _cli_parse_args=["-p", "9000"]).listen_port == 9000
    source = CliSettingsSource(
        Settings, case_sensitive=False, cli_parse_args=["--SERVICE.LISTEN-PORT", "444"]
    )
    assert source()["listen_port"] == "444"


def test_cli_unknown_args() -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_ignore_unknown_args=True
        )
        timeout: int
        remaining: CliUnknownArgs

    result = _settings(
        Settings, _cli_parse_args=["--timeout", "5", "--unused", "value"]
    )
    assert result.remaining == ["--unused", "value"]


def test_cli_enums() -> None:
    class Region(Enum):
        us_east = "east"
        us_west = "west"

    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_kebab_case="all"
        )
        region: Region

    assert (
        _settings(Settings, _cli_parse_args=["--region", "us-east"]).region
        is Region.us_east
    )


def test_cli_subcommands_and_async_execution() -> None:
    class Fetch(BaseModel):
        destination: CliPositionalArg[str]
        complete: bool = False

        async def cli_cmd(self) -> None:
            await asyncio.sleep(0)
            self.complete = True

    class Inspect(BaseModel):
        path: CliPositionalArg[str]

    class App(BaseSettings):
        fetch: CliSubCommand[Fetch]
        inspect: CliSubCommand[Inspect]

        def cli_cmd(self) -> None:
            _ = CliApp.run_subcommand(self)

    result = CliApp.run(App, ["fetch", "archive"])
    assert result.fetch is not None
    assert result.fetch.complete
    assert result.inspect is None
    assert get_subcommand(result) is result.fetch

    async def invoke() -> None:
        result = CliApp.run(App, ["fetch", "archive"])
        assert result.fetch is not None and result.fetch.complete

    asyncio.run(invoke())


def test_cli_no_selected_subcommand() -> None:
    class Build(BaseModel):
        pass

    class App(BaseSettings):
        build: CliSubCommand[Build]

    result = _settings(App, _cli_parse_args=[])
    assert result.build is None
    assert get_subcommand(result, is_required=False) is None
    with pytest.raises(SettingsError, match="subcommand is required"):
        get_subcommand(result, cli_exit_on_error=False)
    with pytest.raises(SystemExit):
        get_subcommand(result)


def test_cli_subcommand_unions() -> None:
    class Upload(BaseModel):
        filename: CliPositionalArg[str]

    class Download(BaseModel):
        url: str

    class App(BaseSettings):
        operation: CliSubCommand[Upload | Download]

    result = _settings(
        App, _cli_parse_args=["Download", "--url", "https://example.test"]
    )
    assert isinstance(result.operation, Download)


def test_cli_run_basemodel_and_dataclass() -> None:
    class Model(BaseModel):
        user_name: str
        verbose: bool = False

        def custom_command(self) -> None:
            self.user_name = self.user_name.upper()

    result = CliApp.run(
        Model,
        ["--user-name", "alex", "--verbose"],
        cli_cmd_method_name="custom_command",
    )
    assert result == Model(user_name="ALEX", verbose=True)

    @dataclass
    class Data:
        count: int

    assert CliApp.run(Data, ["--count", "7"]).count == 7


def test_cli_source_reload_and_parser_integration() -> None:
    class Settings(BaseSettings):
        count: int = 1

    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--external")
    source = CliSettingsSource(Settings, root_parser=parser)
    assert source() == {}
    assert source(args=["--count", "2", "--external", "ignored"]) is source
    assert source() == {"count": "2"}
    assert (
        CliApp.run(Settings, {"count": "3", "external": "ignored"}, source).count == 3
    )
    assert CliApp.run(Settings, SimpleNamespace(count="4"), source).count == 4
    with pytest.raises(SettingsError, match="not both"):
        source(args=[], parsed_args={})


def test_cli_custom_parser_methods() -> None:
    class Settings(BaseSettings):
        count: int = 0

    parser = argparse.ArgumentParser()
    source = CliSettingsSource(
        Settings,
        root_parser=parser,
        parse_args_method=argparse.ArgumentParser.parse_args,
    )
    assert source(args=["--count", "12"])() == {"count": "12"}
    with pytest.raises(SettingsError, match="requires add_argument"):
        _ = CliSettingsSource(Settings, add_argument_method=None)


def test_cli_errors_and_help(capsys: pytest.CaptureFixture[str]) -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_prog_name="demo"
        )
        port: int
        internal: CliSuppress[str] = "hidden"
        secret: str = Field(default="hidden", description=CLI_SUPPRESS)

    with pytest.raises(SettingsError, match="required"):
        _ = _settings(
            Settings,
            _cli_parse_args=[],
            _cli_enforce_required=True,
            _cli_exit_on_error=False,
        )
    with pytest.raises(ValidationError):
        _ = _settings(Settings, _cli_parse_args=[])
    with pytest.raises(SystemExit) as error:
        _ = _settings(Settings, _cli_parse_args=["--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "demo" in output and "--port" in output
    assert "--internal" not in output and "--secret" not in output
    stream = StringIO()
    CliApp.print_help(Settings, file=stream)
    assert stream.getvalue() == CliApp.format_help(Settings)


def test_cli_mutually_exclusive_group() -> None:
    class Selection(CliMutuallyExclusiveGroup):
        name: str | None = None
        index: int | None = None

    class App(BaseModel):
        selection: Selection

    assert CliApp.run(App, ["--selection.index", "3"]).selection.index == 3
    with pytest.raises(SettingsError, match="not allowed with"):
        _ = CliApp.run(
            App,
            ["--selection.name", "task", "--selection.index", "3"],
            cli_exit_on_error=False,
        )


@pytest.mark.parametrize("list_style", ["json", "argparse", "lazy"])
@pytest.mark.parametrize("dict_style", ["json", "env"])
def test_cli_serialization_round_trip(
    list_style: Literal["json", "argparse", "lazy"], dict_style: Literal["json", "env"]
) -> None:
    class Limits(BaseModel):
        budget: dict[str, int]

    class App(BaseModel):
        target: CliPositionalArg[str]
        numbers: list[int]
        limits: Limits
        enabled: bool = False

    instance = App(
        target="release", numbers=[4, 8], limits=Limits(budget={"cpu": 2}), enabled=True
    )
    args = CliApp.serialize(instance, list_style=list_style, dict_style=dict_style)
    assert CliApp.run(App, args) == instance
    assert CliApp.serialize(instance, positionals_first=True)[0] == "release"


def test_cli_serialization_subcommands() -> None:
    class Task(BaseModel):
        filename: CliPositionalArg[str]

    class App(BaseSettings):
        task: CliSubCommand[Task]

    instance = _settings(App, _cli_parse_args=["task", "report"])
    assert CliApp.serialize(instance) == ["task", "report"]


def test_cli_nodecode_and_malformed_collection() -> None:
    class Settings(BaseSettings):
        payload: Annotated[str, NoDecode]
        mapping: dict[str, int] = Field(default_factory=dict)

    assert _settings(Settings, _cli_parse_args=["--payload", "a,b"]).payload == "a,b"
    with pytest.raises(SettingsError, match="key=value"):
        _ = _settings(
            Settings, _cli_parse_args=["--payload", "a", "--mapping", "invalid"]
        )


def test_cli_custom_flag_character() -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_flag_prefix_char="+", cli_implicit_flags=True
        )
        enabled: bool = True

    assert _settings(Settings, _cli_parse_args=["++no-enabled"]).enabled is False


def test_cli_sibling_and_nested_subcommands() -> None:
    class Leaf(BaseModel):
        output_name: str = "out"

    class Parent(BaseModel):
        first: CliSubCommand[Leaf]
        second: CliSubCommand[Leaf]

    class App(BaseSettings):
        left: CliSubCommand[Parent]
        right: CliSubCommand[Parent]

    result = _settings(
        App, _cli_parse_args=["right", "second", "--output_name", "artifact"]
    )
    assert result.left is None
    assert result.right is not None
    assert result.right.first is None
    assert result.right.second is not None
    assert result.right.second.output_name == "artifact"
    assert CliApp.serialize(result) == ["right", "second", "--output_name", "artifact"]
    assert _settings(App, _cli_parse_args=CliApp.serialize(result)) == result


def test_cli_base_model_nested_default_partial_update() -> None:
    class Endpoint(BaseModel):
        host: str = "initial"
        port: int = 1000

    class App(BaseModel):
        endpoint: Endpoint = Endpoint(host="custom")

    assert CliApp.run(App, ["--endpoint.port", "2000"]).endpoint == Endpoint(
        host="custom", port=2000
    )


def test_cli_multiple_aliases_for_nested_model() -> None:
    class Nested(BaseModel):
        value: str

    class App(BaseSettings):
        nested: Nested = Field(validation_alias=AliasChoices("config", "settings"))

    assert (
        _settings(App, _cli_parse_args=["--settings.value", "ok"]).nested.value == "ok"
    )


def test_cli_recursive_model_help() -> None:
    class Node(BaseModel):
        label: str
        child: "Node | None" = None

    class App(BaseSettings):
        node: Node

    assert "--node.child" in CliApp.format_help(App)
    result = _settings(
        App, _cli_parse_args=["--node", '{"label":"root","child":{"label":"leaf"}}']
    )
    assert result.node.child is not None
    assert result.node.child.label == "leaf"


def test_cli_nodecode_collection_before_validator() -> None:
    from pydantic import field_validator

    class App(BaseSettings):
        values: Annotated[list[int], NoDecode]

        @field_validator("values", mode="before")
        @classmethod
        def split_values(cls, value: str) -> list[int]:
            return [int(item) for item in value.split(",")]

    assert _settings(
        App, _cli_parse_args=["--values", "2", "--values", "4"]
    ).values == [2, 4]


def test_cli_invalid_models_and_flags() -> None:
    with pytest.raises(SettingsError, match="Pydantic"):
        _ = CliApp.run(str, [])

    class InvalidFlag(BaseSettings):
        count: CliImplicitFlag[int] = 0  # pyright: ignore[reportInvalidTypeForm]

    with pytest.raises(SettingsError, match="must have type bool"):
        _ = CliSettingsSource(InvalidFlag)

    class InvalidSubcommand(BaseSettings):
        task: CliSubCommand[str]

    with pytest.raises(SettingsError, match="required Pydantic model"):
        _ = CliSettingsSource(InvalidSubcommand)

    class Empty(BaseSettings):
        pass

    with pytest.raises(SettingsError, match="single character"):
        _ = CliSettingsSource(Empty, cli_flag_prefix_char="--")
    with pytest.raises(SettingsError, match="dot-separated"):
        _ = CliSettingsSource(Empty, cli_prefix="invalid.")


def test_cli_subcommand_missing_method() -> None:
    class Child(BaseModel):
        pass

    class App(BaseSettings):
        child: CliSubCommand[Child]

    with pytest.raises(SettingsError, match="missing cli_cmd"):
        _ = CliApp.run_subcommand(_settings(App, _cli_parse_args=["child"]))


def test_cli_help_metavars_and_env_labels() -> None:
    class App(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_hide_none_type=True, cli_show_env_vars=True, env_prefix="APP_"
        )
        maybe: str | None = None

    help_text = CliApp.format_help(App)
    assert "--maybe str" in help_text
    assert "{str,null}" not in help_text
    assert "APP_MAYBE" in help_text


def test_cli_nested_json_merges_and_annotated_unions() -> None:
    class Inner(BaseModel):
        left: int = 0
        right: int = 0

    class Outer(BaseModel):
        inner: Inner

    class App(BaseSettings):
        outer: Outer
        token: Annotated[int, "CLI integer"] | str = "default"

    result = _settings(
        App,
        _cli_parse_args=[
            "--outer",
            '{"inner":{"left":1}}',
            "--outer.inner",
            '{"right":2}',
        ],
    )
    assert result.outer.inner == Inner(left=1, right=2)


def test_cli_json_nested_commas_and_escapes() -> None:
    class App(BaseSettings):
        payload: list[object]
        labels: list[str]

    result = _settings(
        App,
        _cli_parse_args=[
            "--payload",
            '{"items":[1,2],"options":{"x":1,"y":2}}',
            "--labels",
            '"say \\"hello\\", world",plain'.replace("\\\\", "\\"),
        ],
    )
    assert result.payload == [{"items": [1, 2], "options": {"x": 1, "y": 2}}]
    assert result.labels == ['say "hello", world', "plain"]


def test_cli_alias_paths_preserve_nested_model_defaults() -> None:
    class Nested(BaseModel):
        count: int = 2

    class App(BaseModel):
        first: Nested = Field(
            default=Nested(), validation_alias=AliasPath("matrix", 0, 0)
        )
        second: Nested = Field(
            default=Nested(count=4), validation_alias=AliasPath("matrix", 0, 1)
        )

    result = CliApp.run(App, [])
    assert result.first.count == 2
    assert result.second.count == 4


def test_cli_positional_collections_and_optional_positionals() -> None:
    class Many(BaseSettings):
        items: CliPositionalArg[list[int]]

    assert _settings(Many, _cli_parse_args=["1", "2"]).items == [1, 2]
    assert CliApp.serialize(_settings(Many, _cli_parse_args=["1", "2"])) == ["1", "2"]

    class Optional(BaseSettings):
        destination: CliPositionalArg[str] = "default"

    assert _settings(Optional, _cli_parse_args=[]).destination == "default"


def test_cli_literal_and_preserialized_values() -> None:
    class App(BaseSettings):
        action: Literal["start", "stop"] = "start"
        numbers: list[int]
        options: dict[str, int]

    source = CliSettingsSource(App)
    source(parsed_args={"numbers": [1, 3], "options": [{"limit": 2}]})
    assert source()["numbers"] == [1, 3]
    assert source()["options"] == {"limit": 2}
    assert source.get_field_value(App.model_fields["numbers"], "numbers") == (
        [1, 3],
        "numbers",
        False,
    )
    assert "{start,stop}" in CliApp.format_help(App)


def test_cli_invalid_alias_combinations_and_groups() -> None:
    class Child(BaseModel):
        pass

    class MultipleCommands(BaseSettings):
        child: CliSubCommand[Child] = Field(
            validation_alias=AliasChoices("first", "second")
        )

    class MultiplePositionals(BaseSettings):
        value: CliPositionalArg[str] = Field(
            validation_alias=AliasChoices("first", "second")
        )

    class InvalidGroup(CliMutuallyExclusiveGroup):
        child: Child

    class NestedGroup(BaseSettings):
        group: InvalidGroup

    for model in (MultipleCommands, MultiplePositionals):
        with pytest.raises(SettingsError, match="single alias"):
            _ = CliSettingsSource(model)
    with pytest.raises(SettingsError, match="cannot contain nested"):
        _ = CliSettingsSource(NestedGroup)


def test_cli_default_exit_and_suppressed_subcommand_error() -> None:
    class Empty(BaseSettings):
        pass

    with pytest.raises(SystemExit) as raised:
        _ = _settings(Empty, _cli_parse_args=["--unknown"])
    assert raised.value.code == 2
    errors: list[SettingsError | SystemExit] = []
    assert get_subcommand(_settings(Empty), _suppress_errors=errors) is None
    assert len(errors) == 1


def test_cli_serializes_enum_none_unknown_and_defaults() -> None:
    class Choice(Enum):
        first_choice = "first"

    class App(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_kebab_case="all", cli_ignore_unknown_args=True
        )
        choice: Choice
        nullable: str | None
        unchanged: int = 5
        unknown: CliUnknownArgs

    result = _settings(
        App,
        _cli_parse_args=[
            "--choice",
            "first-choice",
            "--nullable",
            "null",
            "--external",
        ],
    )
    serialized = CliApp.serialize(result)
    assert (
        "first-choice" in serialized
        and "null" in serialized
        and "--external" in serialized
    )
    assert "--unchanged" not in serialized
    with pytest.raises(ValueError, match="serialization style"):
        _ = CliApp.serialize(result, list_style="invalid")  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    "annotation", [list[str], list[str | int], list[int | str], list[object]]
)
@pytest.mark.parametrize("token", ["1,2", "[1,2]"])
def test_cli_numeric_list_strings(annotation: Any, token: str) -> None:
    from pydantic import create_model

    model = create_model(
        "NumericTokens", __base__=BaseSettings, values=(annotation, ...)
    )
    assert _settings(model, _cli_parse_args=["--values", token]).model_dump()[
        "values"
    ] == ["1", "2"]


def test_cli_mapping_primitive_types_and_nested_json() -> None:
    class App(BaseSettings):
        mapping: dict[str, str | int | bool | None]
        nested: list[object]

    result = _settings(
        App,
        _cli_parse_args=[
            "--mapping",
            "count=1,enabled=true,empty=null",
            "--nested",
            '[1,[2],{"count":3},true,null]',
        ],
    )
    assert result.mapping == {"count": "1", "enabled": "true", "empty": "null"}
    assert result.nested == ["1", [2], {"count": 3}, True, None]
    result = _settings(
        App,
        _cli_parse_args=[
            "--mapping",
            '{"count":1,"enabled":true,"empty":null}',
            "--nested",
            "[]",
        ],
    )
    assert result.mapping == {"count": 1, "enabled": True, "empty": None}
    assert result.nested == [""]


def test_cli_mapping_alias_paths_and_serialization() -> None:
    class App(BaseSettings):
        token: str = Field(validation_alias=AliasPath("credentials", "token"))
        host: str = Field(validation_alias=AliasPath("servers", 0))
        port: int = Field(validation_alias=AliasPath("servers", 1))

    result = _settings(
        App,
        _cli_parse_args=[
            "--credentials",
            "token=example",
            "--servers",
            "localhost,5432",
        ],
    )
    assert (
        result.token == "example" and result.host == "localhost" and result.port == 5432
    )
    assert _settings(App, _cli_parse_args=CliApp.serialize(result)) == result
    source = CliSettingsSource(App)
    source(
        parsed_args={"credentials": '{"token":"direct"}', "servers": ["remote", "80"]}
    )
    assert source()["credentials"] == {"token": "direct"}


@pytest.mark.parametrize("case_sensitive", [True, False])
@pytest.mark.parametrize("target", ["variable", "alias", "all"])
def test_cli_environment_help_naming(
    case_sensitive: bool, target: Literal["variable", "alias", "all"]
) -> None:
    class Nested(BaseModel):
        value: str = Field("x", validation_alias=AliasChoices("option", "backup"))

    class App(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_show_env_vars=True,
            case_sensitive=case_sensitive,
            env_prefix="App_",
            env_prefix_target=target,
            env_nested_delimiter="__",
            populate_by_name=True,
        )
        nested: Nested = Nested.model_validate({})
        token: str = Field("default", alias="Key")

    help_text = " ".join(CliApp.format_help(App).split())
    prefix = "" if target == "alias" else "App_"
    expected = [
        prefix + "nested__option",
        prefix + "nested__backup",
        prefix + "nested__value",
    ]
    expected = expected if case_sensitive else [value.upper() for value in expected]
    assert " | ".join(expected) in help_text
    alias = ("App_" if target in ("alias", "all") else "") + "Key"
    assert (alias if case_sensitive else alias.upper()) in help_text


def test_cli_nested_environment_help_without_delimiter() -> None:
    class Nested(BaseModel):
        value: str = "default"

    class App(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            cli_show_env_vars=True
        )
        nested: Nested = Nested.model_validate({})

    assert "[env: NESTED]" in CliApp.format_help(App)
    assert "NESTED.VALUE" not in CliApp.format_help(App)


def test_cli_environment_help_runtime_overrides(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Nested(BaseModel):
        value: str = "default"

    class App(BaseSettings):
        nested: Nested = Nested.model_validate({})

    with pytest.raises(SystemExit):
        _ = _settings(
            App,
            _cli_parse_args=["--help"],
            _cli_show_env_vars=True,
            _env_prefix="runtime_",
            _case_sensitive=True,
            _env_nested_delimiter="::",
        )
    assert "runtime_nested::value" in capsys.readouterr().out


def test_cli_command_help_context_and_cleanup() -> None:
    captured: list[str] = []

    class Child(BaseModel):
        value: int = 1

        async def cli_cmd(self) -> None:
            captured.append(CliApp.format_help(self))
            captured.append(CliApp.format_help(type(self)))

    class App(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="APP_"
        )
        parent_value: int = 2
        child: CliSubCommand[Child]

    app = CliApp.run(App, ["child"])

    async def invoke() -> None:
        _ = CliApp.run_subcommand(app, cli_show_env_vars=True)

    asyncio.run(invoke())
    assert "[env: APP_PARENT_VALUE]" in captured[0]
    assert "[env:" not in captured[1]
    assert "[env:" not in CliApp.format_help(app)


def test_cli_empty_list_reference_compatibility() -> None:
    class Strings(BaseSettings):
        values: list[str]

    class Integers(BaseSettings):
        values: list[int]

    assert _settings(Strings, _cli_parse_args=["--values", "[]"]).values == [""]
    with pytest.raises(ValidationError):
        _ = _settings(Integers, _cli_parse_args=["--values", "[]"])
