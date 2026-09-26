"""Original CLI behavior probes that run against independently supplied APIs."""

# Runtime models and metadata come from the public API being compared.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import re
from typing import Any, ClassVar

from pydantic import AliasChoices, AliasPath, BaseModel, Field, create_model


def probe_cli(api: Any) -> dict[str, Any]:
    """Compare CLI values and observable execution behavior, without source access."""
    output: dict[str, Any] = {}

    def record(label: str, model: Any, args: list[str]) -> None:
        try:
            instance = model(_cli_parse_args=args, _cli_exit_on_error=False)
            output[label] = instance.model_dump(mode="json")
        except (ValueError, TypeError, SystemExit) as error:
            output[label] = type(error).__name__

    for annotation in (
        list[str],
        list[int],
        list[str | int],
        list[object],
        list[list[int]],
    ):
        model = create_model(
            "ListTokens", __base__=api.BaseSettings, values=(annotation, ...)
        )
        for token in ("1,2", "[1,2]", "true,null", '[1,[2],{"n":3}]', "[]"):
            record(f"cli-list-{annotation}-{token}", model, ["--values", token])

    for annotation in (
        dict[str, str],
        dict[str, int],
        dict[str, str | int],
        dict[str, object],
    ):
        model = create_model(
            "MappingTokens", __base__=api.BaseSettings, values=(annotation, ...)
        )
        for token in (
            "one=1,two=2",
            "flag=true,empty=null",
            '{"one":1,"flag":true}',
            "{}",
        ):
            record(f"cli-dict-{annotation}-{token}", model, ["--values", token])

    flags = create_model(
        "Flags",
        __base__=api.BaseSettings,
        enabled=(api.CliToggleFlag[bool], True),
        trace=(api.CliDualFlag[bool], False),
        quiet=(api.CliImplicitFlag[bool], False),
        cache=(api.CliExplicitFlag[bool], True),
    )
    for args in (
        [],
        ["--no-enabled", "--trace", "--quiet", "--cache=false"],
        ["--enabled"],
    ):
        record(f"cli-flags-{args}", flags, args)

    class Leaf(BaseModel):
        output_name: str = "default"

    parent = create_model(
        "ParentCommands",
        __base__=BaseModel,
        first=(api.CliSubCommand[Leaf], ...),
        second=(api.CliSubCommand[Leaf], ...),
    )
    app = create_model(
        "RootCommands",
        __base__=api.BaseSettings,
        left=(api.CliSubCommand[parent], ...),
        right=(api.CliSubCommand[parent], ...),
    )
    for args in (
        [],
        ["left", "first"],
        ["right", "second", "--output_name", "artifact"],
    ):
        record(f"cli-subcommands-{args}", app, args)
    selected = app(_cli_parse_args=["right", "second", "--output_name", "artifact"])
    serialized = api.CliApp.serialize(selected)
    output["cli-subcommands-serialized"] = serialized
    output["cli-subcommands-roundtrip"] = app(_cli_parse_args=serialized).model_dump()

    aliases = create_model(
        "Aliases",
        __base__=api.BaseSettings,
        host=(
            str,
            Field(validation_alias=AliasChoices("n", "hostname", AliasPath("pair", 0))),
        ),
        port=(
            int,
            Field(validation_alias=AliasChoices("p", "port", AliasPath("pair", 1))),
        ),
    )
    for args in (["-n", "localhost", "-p", "5432"], ["--pair", "localhost,5432"]):
        record(f"cli-aliases-{args}", aliases, args)
    selected = aliases(_cli_parse_args=["--pair", "localhost,5432"])
    output["cli-aliases-roundtrip"] = aliases(
        _cli_parse_args=api.CliApp.serialize(selected)
    ).model_dump()

    mapping_alias = create_model(
        "MappingAlias",
        __base__=api.BaseSettings,
        token=(str, Field(validation_alias=AliasPath("credentials", "token"))),
    )
    for token in ("token=example", '{"token":"example"}'):
        record(f"cli-mapping-alias-{token}", mapping_alias, ["--credentials", token])

    class Nested(BaseModel):
        value: str = Field("x", validation_alias=AliasChoices("option", "backup"))

    for case_sensitive in (True, False):
        for target in ("variable", "alias", "all"):

            class Help(api.BaseSettings):
                model_config: ClassVar[Any] = api.SettingsConfigDict(
                    cli_show_env_vars=True,
                    case_sensitive=case_sensitive,
                    env_prefix="App_",
                    env_prefix_target=target,
                    env_nested_delimiter="__",
                    populate_by_name=True,
                )
                nested: Nested = Nested.model_validate({})
                token: str = Field("default", alias="Key")

            help_text = " ".join(api.CliApp.format_help(Help).split())
            output[f"cli-env-help-{case_sensitive}-{target}"] = sorted(
                re.findall(r"\[env: ([^]]+)\]", help_text)
            )

    captured: list[bool] = []

    class HelpChild(BaseModel):
        def cli_cmd(self) -> None:
            captured.append("[env:" in api.CliApp.format_help(self))
            captured.append("[env:" in api.CliApp.format_help(type(self)))

    help_app = create_model(
        "HelpApp",
        __base__=api.BaseSettings,
        child=(api.CliSubCommand[HelpChild], ...),
        parent_value=(int, 2),
    )
    instance = api.CliApp.run(help_app, ["child"])
    _ = api.CliApp.run_subcommand(instance, cli_show_env_vars=True)
    captured.append("[env:" in api.CliApp.format_help(instance))
    output["cli-subcommand-help-context"] = captured
    return output
