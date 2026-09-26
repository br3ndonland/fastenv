"""Original source tests covering public settings behavior and fastenv parsing."""

from __future__ import annotations

# Custom settings source hooks intentionally accept arbitrary model field values.
# pyright: reportAny=false, reportExplicitAny=false
import os
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal

import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    Json,
    ValidationError,
)
from pydantic.fields import FieldInfo

from fastenv.settings.sources import (
    DefaultSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    ForceDecode,
    InitSettingsSource,
    NoDecode,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsError,
    canonicalize_inputs,
    deep_merge,
)


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "environ", {})


class Connection(BaseModel):
    host: str = "localhost"
    port: int = 4000
    labels: list[str] = []


class SourceSettings(BaseModel):
    connection: Connection = Connection()
    count: int = 1
    token: str = "default"


def test_environment_prefix_and_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_COUNT", "8")
    monkeypatch.setenv("APP_CONNECTION", '{"host":"db","port":5000}')
    monkeypatch.setenv("COUNT", "90")
    source = EnvSettingsSource(SourceSettings, env_prefix="APP_")
    model = SourceSettings.model_validate(source())
    assert model.count == 8
    assert model.connection == Connection(host="db", port=5000)
    assert source.env_vars["app_count"] == "8"


def test_case_sensitive_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNT", "9")
    assert EnvSettingsSource(SourceSettings, case_sensitive=True)() == {}
    monkeypatch.setenv("count", "10")
    assert EnvSettingsSource(SourceSettings, case_sensitive=True)() == {"count": "10"}


def test_alias_choices_and_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    class Aliased(BaseModel):
        token: str = Field(validation_alias=AliasChoices("PREFERRED", "FALLBACK"))
        count: int = Field(validation_alias=AliasPath("SERIES", 1))
        label: str = Field(alias="DISPLAY")

    monkeypatch.setenv("APP_TOKEN", "ignored")
    monkeypatch.setenv("FALLBACK", "chosen")
    monkeypatch.setenv("SERIES", "[1, 7]")
    monkeypatch.setenv("DISPLAY", "label")
    values = EnvSettingsSource(Aliased, env_prefix="APP_")()
    assert Aliased.model_validate(values).model_dump() == {
        "token": "chosen",
        "count": 7,
        "label": "label",
    }
    monkeypatch.setenv("PREFERRED", "first")
    assert EnvSettingsSource(Aliased)()["PREFERRED"] == "first"


def test_validation_alias_paths_share_a_root(monkeypatch: pytest.MonkeyPatch) -> None:
    class Aliased(BaseModel):
        first: int = Field(validation_alias=AliasPath("GROUP", "first"))
        second: int = Field(validation_alias=AliasPath("GROUP", "second"))

    monkeypatch.setenv("GROUP", '{"first": 3, "second": 9}')
    assert Aliased.model_validate(EnvSettingsSource(Aliased)()).model_dump() == {
        "first": 3,
        "second": 9,
    }


@pytest.mark.parametrize("target", ["variable", "alias", "all"])
def test_prefix_targets(target: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class Aliased(BaseModel):
        label: str = Field(alias="TITLE")
        count: int

    monkeypatch.setenv("TITLE", "bare")
    monkeypatch.setenv("APP_TITLE", "prefixed")
    monkeypatch.setenv("COUNT", "1")
    monkeypatch.setenv("APP_COUNT", "2")
    model = Aliased.model_validate(
        EnvSettingsSource(Aliased, env_prefix="APP_", env_prefix_target=target)()
    )
    assert model.label == ("bare" if target == "variable" else "prefixed")
    assert model.count == (1 if target == "alias" else 2)


def test_nested_values_override_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNECTION", '{"host":"json-host","port":6000}')
    monkeypatch.setenv("CONNECTION__HOST", "nested-host")
    monkeypatch.setenv("CONNECTION__LABELS", '["one", "two"]')
    source = EnvSettingsSource(SourceSettings, env_nested_delimiter="__")
    assert SourceSettings.model_validate(source()).connection == Connection(
        host="nested-host", port=6000, labels=["one", "two"]
    )


def test_nested_max_split_and_mixed_case(monkeypatch: pytest.MonkeyPatch) -> None:
    class Service(BaseModel):
        api_key: str
        retryCount: int

    class Settings(BaseModel):
        service: Service

    monkeypatch.setenv("APP_SERVICE_API_KEY", "secret")
    monkeypatch.setenv("APP_SERVICE_RETRYCOUNT", "6")
    source = EnvSettingsSource(
        Settings, env_prefix="APP_", env_nested_delimiter="_", env_nested_max_split=1
    )
    assert Settings.model_validate(source()).service == Service(
        api_key="secret", retryCount=6
    )


def test_union_scalar_json_and_json_annotation(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings(BaseModel):
        mixed: list[int] | str
        decoded_by_pydantic: Json[list[int]]

    monkeypatch.setenv("MIXED", "not-json")
    monkeypatch.setenv("DECODED_BY_PYDANTIC", "[2, 4]")
    source = EnvSettingsSource(Settings)
    assert source()["mixed"] == "not-json"
    assert source()["decoded_by_pydantic"] == "[2, 4]"
    assert Settings.model_validate(source()).decoded_by_pydantic == [2, 4]
    monkeypatch.setenv("MIXED", "[7, 9]")
    assert EnvSettingsSource(Settings)()["mixed"] == [7, 9]


def test_invalid_json_reports_field_and_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNECTION", "invalid json")
    with pytest.raises(
        SettingsError, match='field "connection".*"EnvSettingsSource"'
    ) as error:
        _ = EnvSettingsSource(SourceSettings)()
    assert isinstance(error.value.__cause__, ValueError)


def test_empty_none_and_enums(monkeypatch: pytest.MonkeyPatch) -> None:
    class Mode(Enum):
        RELEASE = "release"
        DEBUG = "debug"

    class Settings(BaseModel):
        token: str = "fallback"
        count: int | None = 1
        mode: Mode

    monkeypatch.setenv("TOKEN", "")
    monkeypatch.setenv("COUNT", "NONE")
    monkeypatch.setenv("MODE", "RELEASE")
    source = EnvSettingsSource(
        Settings, env_ignore_empty=True, env_parse_none_str="NONE", env_parse_enums=True
    )
    assert Settings.model_validate(source()).model_dump() == {
        "token": "fallback",
        "count": None,
        "mode": Mode.RELEASE,
    }
    assert EnvSettingsSource(SourceSettings)()["token"] == ""


def test_decoding_annotations(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings(BaseModel):
        manual: Annotated[list[int], NoDecode]
        automatic: Annotated[list[int], ForceDecode]
        normal: list[int]

    monkeypatch.setenv("MANUAL", "1,2")
    monkeypatch.setenv("AUTOMATIC", "[3,4]")
    monkeypatch.setenv("NORMAL", "[5,6]")
    source = EnvSettingsSource(Settings)
    source.config["enable_decoding"] = False
    assert source() == {"manual": "1,2", "automatic": [3, 4], "normal": "[5,6]"}


def test_dotenv_multiple_files_and_no_environment_mutation(tmp_path: Path) -> None:
    environment_before = dict(os.environ)
    first = tmp_path / "base.env"
    second = tmp_path / "override.env"
    _ = first.write_text("COUNT=4\nTOKEN='spaces and # hash'\nCONNECTION__HOST=first\n")
    _ = second.write_text("export COUNT=9\nCONNECTION__PORT=7000\n")
    source = DotEnvSettingsSource(
        SourceSettings,
        env_file=[first, tmp_path / "missing", second],
        env_nested_delimiter="__",
    )
    model = SourceSettings.model_validate(source())
    assert model.count == 9
    assert model.token == "spaces and # hash"
    assert model.connection == Connection(host="first", port=7000)
    assert dict(os.environ) == environment_before


def test_dotenv_preserves_case_and_can_disable_file(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    _ = dotenv.write_text("COUNT=3\ncount=4\n")
    source = DotEnvSettingsSource(SourceSettings, env_file=dotenv, case_sensitive=True)
    assert source() == {"count": "4", "COUNT": "3"}
    assert DotEnvSettingsSource(SourceSettings, env_file=None)() == {}


@pytest.mark.parametrize(
    ("filtering", "expected"),
    [
        (None, {"count": "5", "app_unknown": "x", "other": "y"}),
        ("match_prefix", {"count": "5", "unknown": "x"}),
        ("only_existing", {"count": "5"}),
    ],
)
def test_dotenv_filtering(
    tmp_path: Path, filtering: str | None, expected: dict[str, str]
) -> None:
    dotenv = tmp_path / ".env"
    _ = dotenv.write_text("APP_COUNT=5\nAPP_UNKNOWN=x\nOTHER=y\nCOUNT=99\n")
    source = DotEnvSettingsSource(
        SourceSettings, env_file=dotenv, env_prefix="APP_", dotenv_filtering=filtering
    )
    assert source() == expected


def test_dotenv_extra_values_reach_validation(tmp_path: Path) -> None:
    class StrictSettings(SourceSettings):
        model_config: ClassVar[ConfigDict] = {"extra": "forbid"}

    dotenv = tmp_path / ".env"
    _ = dotenv.write_text("UNKNOWN=value\n")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        _ = StrictSettings.model_validate(
            DotEnvSettingsSource(StrictSettings, env_file=dotenv)()
        )


def test_secrets_multiple_directories_and_alias(tmp_path: Path) -> None:
    class Aliased(BaseModel):
        token: str = Field(validation_alias="API_TOKEN")
        connection: Connection

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _ = (first / "API_TOKEN").write_text("  first\n")
    _ = (second / "api_token").write_text("second\n")
    _ = (first / "CONNECTION").write_text('{"host":"secret-host"}')
    model = Aliased.model_validate(
        SecretsSettingsSource(Aliased, secrets_dir=[first, second])()
    )
    assert model.token == "second"
    assert model.connection.host == "secret-host"
    assert SecretsSettingsSource(Aliased)() == {}


def test_secrets_directory_errors(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="does not exist"):
        assert SecretsSettingsSource(SourceSettings, tmp_path / "missing")() == {}
    file = tmp_path / "file"
    _ = file.write_text("text")
    with pytest.raises(SettingsError, match="must reference a directory"):
        _ = SecretsSettingsSource(SourceSettings, file)()
    (tmp_path / "count").mkdir()
    with pytest.warns(UserWarning, match="not a file"):
        assert SecretsSettingsSource(SourceSettings, tmp_path)() == {}


def test_source_state_and_initial_aliases() -> None:
    class Aliased(BaseModel):
        value: str = Field(validation_alias=AliasChoices("FIRST", "SECOND"))

    source = InitSettingsSource(Aliased, {"SECOND": "value"})
    assert source() == {"FIRST": "value"}
    source._set_current_state({"prior": 1})  # pyright: ignore[reportPrivateUsage]
    source._set_settings_sources_data({"previous": {"prior": 1}})  # pyright: ignore[reportPrivateUsage]
    assert source.current_state == {"prior": 1}
    assert source.settings_sources_data == {"previous": {"prior": 1}}
    assert canonicalize_inputs(Aliased, {"FIRST": "one", "SECOND": "two"}) == {
        "FIRST": "one"
    }


def test_nested_default_partial_updates() -> None:
    class Settings(SourceSettings):
        connection: Connection = Connection(host="configured", port=9000)

    assert DefaultSettingsSource(Settings)() == {}
    defaults = DefaultSettingsSource(
        Settings, nested_model_default_partial_update=True
    )()
    assert defaults["connection"] == {"host": "configured", "port": 9000, "labels": []}
    original = Connection(host="init")
    assert (
        InitSettingsSource(Settings, {"connection": original})()["connection"]
        is original
    )
    assert (
        InitSettingsSource(
            Settings, {"connection": original}, nested_model_default_partial_update=True
        )()["connection"]
        == original.model_dump()
    )
    assert (
        deep_merge(defaults, {"connection": {"port": 1234}})["connection"]["host"]
        == "configured"
    )
    assert defaults["connection"]["port"] == 9000


def test_custom_source_decoding_hook() -> None:
    class CustomSource(PydanticBaseSettingsSource):
        def get_field_value(
            self, field: FieldInfo, field_name: str
        ) -> tuple[Any, str, bool]:
            return '["a"]', field_name, True

        def __call__(self) -> dict[str, Any]:
            field = SourceSettings.model_fields["token"]
            value, key, complex_value = self.get_field_value(field, "token")
            return {key: self.prepare_field_value(key, field, value, complex_value)}

    assert CustomSource(SourceSettings)() == {"token": ["a"]}


def test_nested_dictionary_scalar_values(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings(BaseModel):
        labels: dict[str, str]
        arbitrary: dict  # pyright: ignore[reportMissingTypeArgument]
        connection: Connection

    monkeypatch.setenv("LABELS__CODE", "001")
    monkeypatch.setenv("LABELS__JSON", "[1,2]")
    monkeypatch.setenv("ARBITRARY__JSON", "[1,2]")
    monkeypatch.setenv("CONNECTION__UNKNOWN", "123")
    source = EnvSettingsSource(Settings, env_nested_delimiter="__")
    assert source() == {
        "labels": {"code": "001", "json": "[1,2]"},
        "arbitrary": {"json": [1, 2]},
        "connection": {"unknown": "123"},
    }


def test_nested_input_aliases_and_defaults() -> None:
    class Nested(BaseModel):
        item: int = Field(5, validation_alias=AliasChoices("PRIMARY", "SECONDARY"))

    class Settings(BaseModel):
        nested: Nested = Nested.model_validate({"PRIMARY": 7})

    initial = InitSettingsSource(Settings, {"nested": {"SECONDARY": 9}})()
    defaults = DefaultSettingsSource(
        Settings, nested_model_default_partial_update=True
    )()
    assert initial == {"nested": {"PRIMARY": 9}}
    assert defaults == {"nested": {"PRIMARY": 7}}
    assert Settings.model_validate(defaults).nested.item == 7


def test_negative_alias_index(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings(BaseModel):
        last: int = Field(validation_alias=AliasPath("ENTRIES", -1))

    monkeypatch.setenv("ENTRIES", "[3, 5, 7]")
    assert Settings.model_validate(EnvSettingsSource(Settings)()).last == 7


def test_alias_field_name_with_populate_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Settings(BaseModel):
        model_config: ClassVar[ConfigDict] = {"populate_by_name": True}
        token: str = Field(alias="TOKEN_ALIAS")

    monkeypatch.setenv("APP_TOKEN", "by-name")
    source = EnvSettingsSource(Settings, env_prefix="APP_")
    assert source() == {"TOKEN_ALIAS": "by-name"}
    assert InitSettingsSource(
        Settings, {"TOKEN_ALIAS": "alias", "token": "name"}
    )() == {"TOKEN_ALIAS": "alias"}


def test_nested_union_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    class First(BaseModel):
        kind: Literal["first"] = "first"
        first: int = Field(alias="FIRST")

    class Second(BaseModel):
        kind: Literal["second"] = "second"
        second: int = Field(alias="SECOND")

    class Settings(BaseModel):
        choice: First | Second

    monkeypatch.setenv("CHOICE__KIND", "second")
    monkeypatch.setenv("CHOICE__SECOND", "8")
    source = EnvSettingsSource(Settings, env_nested_delimiter="__")
    model = Settings.model_validate(source())
    assert isinstance(model.choice, Second)
    assert model.choice.second == 8


def test_alias_paths_preserve_input_containers() -> None:
    class Settings(BaseModel):
        port: int = Field(validation_alias=AliasPath("SERVERS", 0, "port"))
        last: str = Field(validation_alias=AliasPath("SERVERS", -1, "name"))

    original = {"SERVERS": [{"port": 9000, "extra": True}, {"name": "last"}]}
    values = InitSettingsSource(Settings, original)()
    assert values == original
    assert values["SERVERS"] is not original["SERVERS"]
    assert Settings.model_validate(values).port == 9000


def test_alias_paths_construct_lists_from_choices() -> None:
    class Settings(BaseModel):
        port: int = Field(
            validation_alias=AliasChoices(AliasPath("SERVERS", 0, "port"), "PORT")
        )

    assert InitSettingsSource(Settings, {"PORT": 9010})() == {
        "SERVERS": [{"port": 9010}]
    }
    # Strings cannot be indexed to provide an AliasPath value.
    assert InitSettingsSource(Settings, {"SERVERS": "port"})() == {"SERVERS": "port"}


def test_conflicting_alias_container_types() -> None:
    class Settings(BaseModel):
        numeric: int = Field(
            validation_alias=AliasChoices(AliasPath("ROOT", 0), "NUMBER")
        )
        named: int = Field(
            validation_alias=AliasChoices(AliasPath("ROOT", "key"), "NAME")
        )

    with pytest.raises(SettingsError, match="integer index"):
        _ = InitSettingsSource(Settings, {"NUMBER": 1, "NAME": 2})()


def test_shared_alias_can_use_distinct_field_names() -> None:
    class Settings(BaseModel):
        model_config: ClassVar[ConfigDict] = {"populate_by_name": True}
        previous: str = Field(alias="TOKEN")
        latest: str = Field(alias="TOKEN")

    values = InitSettingsSource(Settings, {"previous": "old", "latest": "new"})()
    assert values == {"previous": "old", "latest": "new"}
    assert Settings.model_validate(values).latest == "new"
    assert InitSettingsSource(Settings, {"previous": "old", "TOKEN": "alias"})() == {
        "previous": "alias",
        "latest": "alias",
    }


def test_dataclass_default_partial_update() -> None:
    from dataclasses import dataclass

    @dataclass
    class Nested:
        port: int = 9100

    class Settings(BaseModel):
        nested: Nested = Field(default=Nested())

    source = DefaultSettingsSource(Settings, nested_model_default_partial_update=True)
    assert source() == {"nested": {"port": 9100}}
    assert source.get_field_value(Settings.model_fields["nested"], "nested") == (
        {"port": 9100},
        "nested",
        False,
    )
    initial = InitSettingsSource(Settings, {"nested": Nested(port=9200)})
    assert initial.get_field_value(Settings.model_fields["nested"], "nested") == (
        Nested(port=9200),
        "nested",
        False,
    )


def test_source_read_failure_preserves_cause() -> None:
    class FailingSource(EnvSettingsSource):
        def get_field_value(
            self, field: FieldInfo, field_name: str
        ) -> tuple[Any, str, bool]:
            raise OSError("cannot read backing store")

    with pytest.raises(
        SettingsError, match='getting value for field "connection"'
    ) as error:
        _ = FailingSource(SourceSettings)()
    assert isinstance(error.value.__cause__, OSError)


def test_annotated_union_decoding(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings(BaseModel):
        values: str | Annotated[list[str], "list-option"]

    monkeypatch.setenv("VALUES", '["a"]')
    assert EnvSettingsSource(Settings)() == {"values": ["a"]}


def test_optional_enum_and_unknown_nested_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Mode(Enum):
        ACTIVE = "active"

    class Settings(BaseModel):
        mode: int | Mode | None
        connection: Connection | None = None

    monkeypatch.setenv("MODE", "ACTIVE")
    monkeypatch.setenv("CONNECTION__MISSING", "ignored")
    source = EnvSettingsSource(
        Settings, env_parse_enums=True, env_nested_delimiter="__"
    )
    assert source()["mode"] is Mode.ACTIVE
    assert source()["connection"] == {"missing": "ignored"}


def test_deep_nested_values_and_decode_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class Nested(BaseModel):
        connection: Connection
        choice: list[str] | str

    class Settings(BaseModel):
        service: Nested
        arbitrary: dict  # pyright: ignore[reportMissingTypeArgument]

    monkeypatch.setenv("SERVICE__CONNECTION__PORT", "8100")
    monkeypatch.setenv("SERVICE__CHOICE", "plain text")
    monkeypatch.setenv("ARBITRARY__TEXT", "not json")
    source = EnvSettingsSource(Settings, env_nested_delimiter="__")
    assert Settings.model_validate(source()).service.connection.port == 8100
    assert source()["arbitrary"] == {"text": "not json"}
    monkeypatch.setenv("SERVICE__CONNECTION__LABELS", "invalid json")
    with pytest.raises(SettingsError, match='parsing value for field "service"'):
        _ = EnvSettingsSource(Settings, env_nested_delimiter="__")()


def test_incomplete_annotation_warning() -> None:
    from typing import ForwardRef

    from pydantic import create_model

    from fastenv.settings import IncompleteFieldDefinitionWarning

    settings = create_model(
        "UnresolvedSettings", pending=(ForwardRef("LaterModel"), ...)
    )
    with pytest.warns(
        IncompleteFieldDefinitionWarning, match="pending.*forward reference"
    ):
        source = InitSettingsSource(settings, {})
    assert source() == {}
    with pytest.warns(IncompleteFieldDefinitionWarning, match="model_rebuild"):
        assert EnvSettingsSource(settings)() == {}


def test_init_names_are_case_insensitive_only_at_top_level() -> None:
    class Nested(BaseModel):
        model_config: ClassVar[ConfigDict] = {"extra": "forbid"}
        value: int = Field(alias="VALUE")

    class Settings(BaseModel):
        model_config: ClassVar[ConfigDict] = {"extra": "forbid"}
        nested: Nested
        count: int

    source = InitSettingsSource(Settings, {"NESTED": {"VALUE": 1}, "COUNT": 2})
    assert Settings.model_validate(source()).count == 2
    source.config["case_sensitive"] = True
    assert source() == {"NESTED": {"VALUE": 1}, "COUNT": 2}
    with pytest.raises(ValidationError, match="missing"):
        _ = Settings.model_validate(source())
    nested_unknown = InitSettingsSource(
        Settings, {"nested": {"VALUE": 1, "value": 2}, "count": 2}
    )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        _ = Settings.model_validate(nested_unknown())


def test_init_unknown_names_remain_extra_inputs() -> None:
    class Settings(BaseModel):
        model_config: ClassVar[ConfigDict] = {"extra": "forbid"}
        value: int = Field(alias="ALIAS")

    source = InitSettingsSource(Settings, {"ALIAS": 1, "value": 2})
    assert source() == {"ALIAS": 1, "value": 2}
    with pytest.raises(ValidationError, match="extra_forbidden"):
        _ = Settings.model_validate(source())
    assert InitSettingsSource(Settings, {"alias": 2, "ALIAS": 1})() == {"ALIAS": 2}


def test_alias_path_preserves_tuple_inputs() -> None:
    class Settings(BaseModel):
        value: int = Field(validation_alias=AliasPath("ITEMS", 0))

    original = {"ITEMS": (1, 2)}
    values = InitSettingsSource(Settings, original)()
    assert values == original
    assert Settings.model_validate(values).value == 1
