# Custom settings source hooks intentionally accept arbitrary model field values.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import dataclasses
import json
import os
import threading
import tomllib
import zipfile
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, ForwardRef, Literal, cast

import anyio
import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    Json,
    ValidationError,
    create_model,
)
from pydantic.fields import FieldInfo

from fastenv.settings import pydantic_settings_sources
from fastenv.settings.pydantic_settings import BaseSettings, SettingsConfigDict
from fastenv.settings.pydantic_settings_sources import (
    DefaultSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    ForceDecode,
    IncompleteFieldDefinitionWarning,
    InitSettingsSource,
    JsonConfigSettingsSource,
    NestedSecretsSettingsSource,
    NoDecode,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SecretsSettingsSource,
    SettingsError,
    TomlConfigSettingsSource,
    canonicalize_inputs,
    deep_merge,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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


class Service(BaseModel):
    hostname: str = "localhost"
    port: int = 8000


class FileSettings(BaseSettings):
    service: Service = Service()
    token: str = "default"


class TestEnvironmentSource:
    """Test environment variable names, nested values, and decoding."""

    def test_environment_prefix_and_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Read prefixed variables and decode JSON for nested models."""
        monkeypatch.setenv("APP_COUNT", "8")
        monkeypatch.setenv("APP_CONNECTION", '{"host":"db","port":5000}')
        monkeypatch.setenv("COUNT", "90")
        source = EnvSettingsSource(SourceSettings, env_prefix="APP_")
        model = SourceSettings.model_validate(source())
        assert model.count == 8
        assert model.connection == Connection(host="db", port=5000)
        assert source.env_vars["app_count"] == "8"

    def test_case_sensitive_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Require matching letter case when case-sensitive names are enabled."""
        monkeypatch.setenv("COUNT", "9")
        assert EnvSettingsSource(SourceSettings, case_sensitive=True)() == {}
        monkeypatch.setenv("count", "10")
        assert EnvSettingsSource(SourceSettings, case_sensitive=True)() == {
            "count": "10"
        }

    @pytest.mark.parametrize("target", ["variable", "alias", "all"])
    def test_prefix_targets(self, target: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Apply prefixes to field names, aliases, or both as configured."""

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

    def test_nested_values_override_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Let separate nested variables override values in a JSON object."""
        monkeypatch.setenv("CONNECTION", '{"host":"json-host","port":6000}')
        monkeypatch.setenv("CONNECTION__HOST", "nested-host")
        monkeypatch.setenv("CONNECTION__LABELS", '["one", "two"]')
        source = EnvSettingsSource(SourceSettings, env_nested_delimiter="__")
        assert SourceSettings.model_validate(source()).connection == Connection(
            host="nested-host", port=6000, labels=["one", "two"]
        )

    def test_nested_max_split_and_mixed_case(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Limit name splitting and match nested field names with mixed letter case."""

        class Service(BaseModel):
            api_key: str
            retryCount: int

        class Settings(BaseModel):
            service: Service

        monkeypatch.setenv("APP_SERVICE_API_KEY", "secret")
        monkeypatch.setenv("APP_SERVICE_RETRYCOUNT", "6")
        source = EnvSettingsSource(
            Settings,
            env_prefix="APP_",
            env_nested_delimiter="_",
            env_nested_max_split=1,
        )
        assert Settings.model_validate(source()).service == Service(
            api_key="secret", retryCount=6
        )

    def test_union_scalar_json_and_json_annotation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handle union values as text or JSON and preserve Pydantic JSON annotations."""

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

    def test_invalid_json_reports_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Name the field and keep the original error when JSON decoding fails."""
        monkeypatch.setenv("CONNECTION", "invalid json")
        with pytest.raises(SettingsError, match="connection") as error:
            _ = EnvSettingsSource(SourceSettings)()
        assert isinstance(error.value.__cause__, ValueError)

    def test_empty_none_and_enums(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handle empty strings, configured null values, and enum names."""

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
            Settings,
            env_ignore_empty=True,
            env_parse_none_str="NONE",
            env_parse_enums=True,
        )
        assert Settings.model_validate(source()).model_dump() == {
            "token": "fallback",
            "count": None,
            "mode": Mode.RELEASE,
        }
        assert EnvSettingsSource(SourceSettings)()["token"] == ""

    def test_decoding_annotations(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Allow field annotations to enable or disable JSON decoding."""

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

    def test_nested_dictionary_scalar_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preserve string dictionary values and decode untyped dictionary values."""

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

    def test_annotated_union_decoding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Decode JSON for a union wrapped in an Annotated type."""

        class Settings(BaseModel):
            values: str | Annotated[list[str], "list-option"]

        monkeypatch.setenv("VALUES", '["a"]')
        assert EnvSettingsSource(Settings)() == {"values": ["a"]}

    def test_optional_enum_and_unknown_nested_union(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Parse optional enums and preserve unknown fields in nested union values."""

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

    def test_deep_nested_values_and_decode_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read deeply nested variables and report invalid JSON for model fields."""

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
        with pytest.raises(SettingsError, match="service"):
            _ = EnvSettingsSource(Settings, env_nested_delimiter="__")()

    def test_incomplete_annotation_warning(self) -> None:
        """Warn about unresolved field types and explain how to rebuild the model."""
        pending_annotation: Any = ForwardRef("LaterModel")
        settings = create_model("UnresolvedSettings", pending=(pending_annotation, ...))
        with pytest.warns(IncompleteFieldDefinitionWarning, match="pending"):
            source = InitSettingsSource(settings, {})
        assert source() == {}
        with pytest.warns(IncompleteFieldDefinitionWarning, match="model_rebuild"):
            assert EnvSettingsSource(settings)() == {}


class TestSourceAliases:
    """Test alternate field names and nested alias paths."""

    def test_alias_choices_and_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Choose the first available alias and read values from nested alias paths."""

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

    def test_validation_alias_paths_share_a_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read multiple fields from alias paths with the same root."""

        class Aliased(BaseModel):
            first: int = Field(validation_alias=AliasPath("GROUP", "first"))
            second: int = Field(validation_alias=AliasPath("GROUP", "second"))

        monkeypatch.setenv("GROUP", '{"first": 3, "second": 9}')
        assert Aliased.model_validate(EnvSettingsSource(Aliased)()).model_dump() == {
            "first": 3,
            "second": 9,
        }

    def test_nested_input_aliases_and_defaults(self) -> None:
        """Use nested field aliases for constructor inputs and default values."""

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

    def test_negative_alias_index(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Read the last list item through a negative alias index."""

        class Settings(BaseModel):
            last: int = Field(validation_alias=AliasPath("ENTRIES", -1))

        monkeypatch.setenv("ENTRIES", "[3, 5, 7]")
        assert Settings.model_validate(EnvSettingsSource(Settings)()).last == 7

    def test_alias_field_name_with_populate_by_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Accept field names when enabled and prefer an explicitly supplied alias."""

        class Settings(BaseModel):
            model_config: ClassVar[ConfigDict] = {"populate_by_name": True}
            token: str = Field(alias="TOKEN_ALIAS")

        monkeypatch.setenv("APP_TOKEN", "by-name")
        source = EnvSettingsSource(Settings, env_prefix="APP_")
        assert source() == {"TOKEN_ALIAS": "by-name"}
        assert InitSettingsSource(
            Settings, {"TOKEN_ALIAS": "alias", "token": "name"}
        )() == {"TOKEN_ALIAS": "alias"}

    def test_nested_union_aliases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Match aliases for the selected model in a nested union."""

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

    def test_alias_paths_preserve_input_containers(self) -> None:
        """Copy alias containers without changing the caller's inputs."""

        class Settings(BaseModel):
            port: int = Field(validation_alias=AliasPath("SERVERS", 0, "port"))
            last: str = Field(validation_alias=AliasPath("SERVERS", -1, "name"))

        original = {"SERVERS": [{"port": 9000, "extra": True}, {"name": "last"}]}
        values = InitSettingsSource(Settings, original)()
        assert values == original
        assert values["SERVERS"] is not original["SERVERS"]
        assert Settings.model_validate(values).port == 9000

    def test_alias_paths_construct_lists_from_choices(self) -> None:
        """Build nested list aliases while leaving scalar inputs for validation."""

        class Settings(BaseModel):
            port: int = Field(
                validation_alias=AliasChoices(AliasPath("SERVERS", 0, "port"), "PORT")
            )

        assert InitSettingsSource(Settings, {"PORT": 9010})() == {
            "SERVERS": [{"port": 9010}]
        }
        # Strings cannot be indexed to provide an AliasPath value.
        assert InitSettingsSource(Settings, {"SERVERS": "port"})() == {
            "SERVERS": "port"
        }

    def test_conflicting_alias_container_types(self) -> None:
        """Reject a string alias key where a list index is required."""

        class Settings(BaseModel):
            numeric: int = Field(
                validation_alias=AliasChoices(AliasPath("ROOT", 0), "NUMBER")
            )
            named: int = Field(
                validation_alias=AliasChoices(AliasPath("ROOT", "key"), "NAME")
            )

        with pytest.raises(SettingsError, match="integer index"):
            _ = InitSettingsSource(Settings, {"NUMBER": 1, "NAME": 2})()

    def test_shared_alias_can_use_distinct_field_names(self) -> None:
        """Keep distinct field-name values for fields sharing the same alias."""

        class Settings(BaseModel):
            model_config: ClassVar[ConfigDict] = {"populate_by_name": True}
            previous: str = Field(alias="TOKEN")
            latest: str = Field(alias="TOKEN")

        values = InitSettingsSource(Settings, {"previous": "old", "latest": "new"})()
        assert values == {"previous": "old", "latest": "new"}
        assert Settings.model_validate(values).latest == "new"
        assert InitSettingsSource(
            Settings, {"previous": "old", "TOKEN": "alias"}
        )() == {
            "previous": "alias",
            "latest": "alias",
        }

    def test_alias_path_preserves_tuple_inputs(self) -> None:
        """Preserve tuple values when copying inputs for an alias path."""

        class Settings(BaseModel):
            value: int = Field(validation_alias=AliasPath("ITEMS", 0))

        original = {"ITEMS": (1, 2)}
        values = InitSettingsSource(Settings, original)()
        assert values == original
        assert Settings.model_validate(values).value == 1


class TestDotenvSource:
    """Test dotenv file priority, filtering, and environment isolation."""

    def test_dotenv_multiple_files_and_no_environment_mutation(
        self, tmp_path: Path
    ) -> None:
        """Prefer later dotenv files without changing the process environment."""
        environment_before = dict(os.environ)
        first = tmp_path / "base.env"
        second = tmp_path / "override.env"
        _ = first.write_text(
            "COUNT=4\nTOKEN='spaces and # hash'\nCONNECTION__HOST=first\n"
        )
        _ = second.write_text(
            "export COUNT=9\nCONNECTION__PORT=7000\nCONNECTION__LABELS='[\"caf\xe9\"]'\n",
            encoding="latin-1",
        )
        source = DotEnvSettingsSource(
            SourceSettings,
            env_file=[first, tmp_path / "missing", second],
            env_file_encoding="latin-1",
            env_nested_delimiter="__",
        )
        model = SourceSettings.model_validate(source())
        assert model.count == 9
        assert model.token == "spaces and # hash"
        assert model.connection == Connection(
            host="first", port=7000, labels=["caf\xe9"]
        )
        assert dict(os.environ) == environment_before

    def test_dotenv_files_are_logged(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Log the number of variables loaded from each dotenv file that exists."""
        first = tmp_path / "base.env"
        second = tmp_path / "override.env"
        _ = first.write_text("COUNT=4\nTOKEN=first\n")
        _ = second.write_text("COUNT=9\nTOKEN=second\nCONNECTION__PORT=7000\n")
        logger = mocker.patch.object(pydantic_settings_sources, "logger", autospec=True)
        _ = DotEnvSettingsSource(
            SourceSettings, env_file=[first, tmp_path / "missing", second]
        )()
        assert logger.info.call_count == 2
        logger.info.assert_any_call(f"fastenv loaded 2 variables from {first}")
        logger.info.assert_any_call(f"fastenv loaded 3 variables from {second}")

    def test_dotenv_case_null_and_empty_values(self, tmp_path: Path) -> None:
        """Honor key case, null markers, and empty values, or disable the file."""
        dotenv = tmp_path / ".env"
        _ = dotenv.write_text("COUNT=3\ncount=4\ntoken=nil\nconnection=\n")
        source = DotEnvSettingsSource(
            SourceSettings,
            env_file=dotenv,
            case_sensitive=True,
            env_parse_none_str="nil",
            env_ignore_empty=True,
        )
        assert source() == {"count": "4", "COUNT": "3", "token": None}
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
        self, tmp_path: Path, filtering: str | None, expected: dict[str, str]
    ) -> None:
        """Keep dotenv values according to the configured filtering policy."""
        dotenv = tmp_path / ".env"
        _ = dotenv.write_text("APP_COUNT=5\nAPP_UNKNOWN=x\nOTHER=y\nCOUNT=99\n")
        source = DotEnvSettingsSource(
            SourceSettings,
            env_file=dotenv,
            env_prefix="APP_",
            dotenv_filtering=filtering,
        )
        assert source() == expected

    def test_dotenv_extra_values_reach_validation(self, tmp_path: Path) -> None:
        """Pass unknown dotenv values to Pydantic for extra-field validation."""

        class StrictSettings(SourceSettings):
            model_config: ClassVar[ConfigDict] = {"extra": "forbid"}

        dotenv = tmp_path / ".env"
        _ = dotenv.write_text("UNKNOWN=value\n")
        with pytest.raises(ValidationError, match="extra_forbidden"):
            _ = StrictSettings.model_validate(
                DotEnvSettingsSource(StrictSettings, env_file=dotenv)()
            )


class TestSecretsSource:
    """Test secret file priority and directory errors."""

    def test_secrets_multiple_directories_and_aliases(self, tmp_path: Path) -> None:
        """Prefer later directories for a name, but keep alias order across them."""

        class Aliased(BaseModel):
            token: str = Field(validation_alias=AliasChoices("API_TOKEN", "FALLBACK"))
            connection: Connection

        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        _ = (first / "API_TOKEN").write_text("  first\n")
        _ = (second / "FALLBACK").write_text("second\n")
        _ = (first / "CONNECTION").write_text('{"host":"first-host"}')
        _ = (second / "connection").write_text('{"host":"second-host"}')
        model = Aliased.model_validate(
            SecretsSettingsSource(Aliased, secrets_dir=[first, second])()
        )
        assert model.token == "first"
        assert model.connection.host == "second-host"
        assert SecretsSettingsSource(Aliased)() == {}

    def test_secrets_directory_errors(self, tmp_path: Path) -> None:
        """Warn about missing files and reject secret paths that are not directories."""
        with pytest.warns(UserWarning, match="does not exist"):
            assert SecretsSettingsSource(SourceSettings, tmp_path / "missing")() == {}
        file = tmp_path / "file"
        _ = file.write_text("text")
        with pytest.raises(SettingsError, match="must reference a directory"):
            _ = SecretsSettingsSource(SourceSettings, file)()
        (tmp_path / "count").mkdir()
        with pytest.warns(UserWarning, match="not a file"):
            assert SecretsSettingsSource(SourceSettings, tmp_path)() == {}


class TestNestedSecretsSource:
    """Test secret directory options and file size limits."""

    def test_nested_secrets_overrides_and_no_environment_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prefer later secret directories without reading process environment values."""
        first, last = tmp_path / "first", tmp_path / "last"
        first.mkdir()
        last.mkdir()
        _ = (first / "APP_SERVICE__PORT").write_text("9000\n")
        _ = (first / "APP_SERVICE__HOSTNAME").write_text("secrets\n")
        _ = (last / "APP_SERVICE__PORT").write_text("9001\n")
        monkeypatch.setenv("APP_TOKEN", "must-not-load")

        class Configured(FileSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", secrets_dir=[first, last]
            )

        source = NestedSecretsSettingsSource(SecretsSettingsSource(Configured))
        assert source() == {"service": {"hostname": "secrets", "port": "9001"}}
        assert (
            NestedSecretsSettingsSource(Configured, secrets_dir=first)()["service"][
                "port"
            ]
            == "9000"
        )

    def test_nested_secret_subdirectories_and_config_overrides(
        self, tmp_path: Path
    ) -> None:
        """Read nested fields from subdirectories and reject conflicting separators."""
        service = tmp_path / "service"
        service.mkdir()
        _ = (service / "port").write_text("9100")
        _ = (tmp_path / "token").write_text("secret")

        class Configured(FileSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                secrets_dir=tmp_path,
                env_prefix="UNUSED_",
                secrets_prefix="",
                secrets_nested_subdir=True,
            )

        assert NestedSecretsSettingsSource(Configured)() == {
            "service": {"port": "9100"},
            "token": "secret",
        }
        with pytest.raises(SettingsError, match="mutually exclusive"):
            _ = NestedSecretsSettingsSource(Configured, secrets_nested_delimiter="__")

    def test_nested_secret_prefix_case_and_delimiter(self, tmp_path: Path) -> None:
        """Honor prefixes, letter case, and separators in secret filenames."""
        _ = (tmp_path / "APP_TOKEN").write_text("upper")
        _ = (tmp_path / "APP_service_port").write_text("9200")
        _ = (tmp_path / "token").write_text("unprefixed")
        source = NestedSecretsSettingsSource(
            FileSettings,
            secrets_dir=tmp_path,
            secrets_prefix="APP_",
            secrets_nested_delimiter="_",
            secrets_case_sensitive=True,
        )
        assert source() == {"service": {"port": "9200"}}
        assert (
            NestedSecretsSettingsSource(
                FileSettings, secrets_dir=tmp_path, secrets_prefix="APP_"
            )()["token"]
            == "upper"
        )

    def test_nested_secret_missing_and_size_limits(self, tmp_path: Path) -> None:
        """Apply missing-directory policies and reject invalid or oversized directories."""
        missing = tmp_path / "missing"
        assert NestedSecretsSettingsSource(FileSettings)() == {}
        assert (
            NestedSecretsSettingsSource(
                FileSettings, secrets_dir=missing, secrets_dir_missing="ok"
            )()
            == {}
        )
        with pytest.warns(UserWarning, match="does not exist"):
            _ = NestedSecretsSettingsSource(FileSettings, secrets_dir=missing)()
        with pytest.raises(SettingsError, match="does not exist"):
            _ = NestedSecretsSettingsSource(
                FileSettings, secrets_dir=missing, secrets_dir_missing="error"
            )()
        secret = tmp_path / "token"
        _ = secret.write_text("large")
        with pytest.raises(SettingsError, match="maximum size"):
            _ = NestedSecretsSettingsSource(
                FileSettings, secrets_dir=tmp_path, secrets_dir_max_size=4
            )()
        with pytest.raises(SettingsError, match="not a directory"):
            _ = NestedSecretsSettingsSource(FileSettings, secrets_dir=secret)()

    def test_nested_secret_rejects_invalid_missing_directory_policy(self) -> None:
        """Reject an unknown policy for missing secret directories."""

        class Invalid(FileSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict()

        cast(Any, Invalid.model_config)["secrets_dir_missing"] = "ignore-typo"
        with pytest.raises(SettingsError, match="secrets_dir_missing"):
            _ = NestedSecretsSettingsSource(Invalid)

    def test_nested_secret_size_limit_handles_file_growth(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Enforce the combined size limit when secret files grow while being read."""
        for name in ("hostname", "token"):
            _ = (tmp_path / name).write_text("x")
        original_open = Path.open

        def grow_before_read(path: Path, mode: str, *args: Any, **kwargs: Any):
            if path.parent == tmp_path and mode == "rb":
                with original_open(path, "w") as stream:
                    _ = stream.write("grown")
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "open", grow_before_read)
        with pytest.raises(SettingsError, match="maximum size"):
            _ = NestedSecretsSettingsSource(
                FileSettings, secrets_dir=tmp_path, secrets_dir_max_size=8
            )()


class TestConfigFileSources:
    """Test JSON, TOML, and package resource loading."""

    @pytest.mark.parametrize("deep", [False, True])
    @pytest.mark.parametrize("format", ["json", "toml"])
    def test_config_files_merge_in_order(
        self, tmp_path: Path, format: str, deep: bool
    ) -> None:
        """Merge files in order, replacing or deep merging nested tables."""
        contents = {
            "json": (
                '{"token":"base","service":{"hostname":"first","port":9000}}',
                '{"service":{"port":9001}}',
            ),
            "toml": (
                'token="base"\n[service]\nhostname="first"\nport=9000',
                "[service]\nport=9001",
            ),
        }
        source_class = {
            "json": JsonConfigSettingsSource,
            "toml": TomlConfigSettingsSource,
        }[format]
        files = [tmp_path / f"base.{format}", tmp_path / f"override.{format}"]
        for path, content in zip(files, contents[format]):
            _ = path.write_text(content)
        source = source_class(FileSettings, files, deep_merge=deep)
        expected_service: dict[str, int | str] = {"port": 9001}
        if deep:
            expected_service["hostname"] = "first"
        assert source() == {"token": "base", "service": expected_service}

    @pytest.mark.parametrize("format", ["json", "toml"])
    def test_config_file_model_config_and_disable(
        self, tmp_path: Path, format: str
    ) -> None:
        """Use configured file paths and ignore disabled or missing files."""
        source_class = {
            "json": JsonConfigSettingsSource,
            "toml": TomlConfigSettingsSource,
        }[format]
        path = tmp_path / f"config.{format}"
        _ = path.write_text(
            {
                "json": '{"token":"configured"}',
                "toml": 'token="configured"',
            }[format]
        )

        class Configured(FileSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                json_file=path if format == "json" else None,
                toml_file=path if format == "toml" else None,
            )

        assert source_class(Configured)() == {"token": "configured"}
        assert source_class(Configured, None)() == {}
        assert source_class(Configured, tmp_path / "missing")() == {}
        assert source_class(Configured, tmp_path)() == {}

    def test_config_files_are_logged(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Log the number of top-level keys loaded from each file that exists."""
        path = tmp_path / "config.json"
        _ = path.write_text(
            '{"token":"configured","service":{"hostname":"first","port":9000}}'
        )
        logger = mocker.patch.object(pydantic_settings_sources, "logger", autospec=True)
        _ = JsonConfigSettingsSource(FileSettings, [tmp_path / "missing", path])()
        logger.info.assert_called_once_with(f"fastenv loaded 2 variables from {path}")

    def test_json_encoding_alias_and_settings_integration(self, tmp_path: Path) -> None:
        """Load encoded JSON values through aliases and allow constructor overrides."""
        path = tmp_path / "config.json"
        _ = path.write_bytes('{"API_TOKEN":"caf\\u00e9"}'.encode("utf-16"))

        class Configured(BaseSettings):
            token: str = Field(default="", alias="API_TOKEN")
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                json_file=path, json_file_encoding="utf-16"
            )

            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls: type[BaseSettings],
                init_settings: PydanticBaseSettingsSource,
                env_settings: PydanticBaseSettingsSource,
                dotenv_settings: PydanticBaseSettingsSource,
                file_secret_settings: PydanticBaseSettingsSource,
            ) -> tuple[PydanticBaseSettingsSource, ...]:
                return init_settings, JsonConfigSettingsSource(settings_cls)

        assert Configured().token == "caf\u00e9"
        assert Configured(API_TOKEN="override").token == "override"
        source = JsonConfigSettingsSource(Configured)
        assert source.get_field_value(Configured.model_fields["token"], "token") == (
            None,
            "",
            False,
        )

    @pytest.mark.parametrize(
        ("source_class", "contents", "error"),
        [
            (JsonConfigSettingsSource, "5", SettingsError),
            (JsonConfigSettingsSource, "{", json.JSONDecodeError),
            (TomlConfigSettingsSource, "[", tomllib.TOMLDecodeError),
        ],
    )
    def test_invalid_configuration_files(
        self,
        tmp_path: Path,
        source_class: type[JsonConfigSettingsSource | TomlConfigSettingsSource],
        contents: str,
        error: type[Exception],
    ) -> None:
        """Reject files that do not parse or do not contain a mapping."""
        path = tmp_path / "config"
        _ = path.write_text(contents)
        with pytest.raises(error):
            _ = source_class(FileSettings, path)()

    @pytest.mark.anyio
    async def test_file_resources_without_filesystem_paths(
        self, tmp_path: Path
    ) -> None:
        """Read JSON from a ZIP archive resource, off the event loop when loading."""
        archive = tmp_path / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("settings.json", '{"token":"resource"}')
        event_loop_thread = threading.get_ident()

        class Resource(zipfile.Path):
            def read_text(self, *args: Any, **kwargs: Any) -> str:
                assert threading.get_ident() != event_loop_thread
                return super().read_text(*args, **kwargs)

        with zipfile.ZipFile(archive) as bundle:
            source = JsonConfigSettingsSource(
                FileSettings,
                [Resource(bundle, "missing.json"), Resource(bundle, "settings.json")],
            )
            assert await source.load() == {"token": "resource"}

    def test_toml_table_selection(self, tmp_path: Path) -> None:
        """Read a selected TOML table and reject missing or non-table selections."""
        toml = tmp_path / "config.toml"
        _ = toml.write_text('scalar="value"\n[app.runtime]\ntoken="selected"')

        class Configured(FileSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                toml_file=toml,
                toml_table_header=("app", "runtime"),
            )

        assert TomlConfigSettingsSource(Configured)() == {"token": "selected"}
        with pytest.raises(KeyError):
            _ = TomlConfigSettingsSource(Configured, toml_table_header=("missing",))()
        with pytest.raises(SettingsError, match="mapping"):
            _ = TomlConfigSettingsSource(
                Configured, toml_table_header=("scalar", "nested")
            )()

    def test_pyproject_search_depth_explicit_file_and_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Support pyproject search limits, explicit paths, and root-level settings."""
        project = tmp_path / "pyproject.toml"
        _ = project.write_text('token="root"\n[tool.pydantic-settings]\ntoken="table"')
        work = tmp_path / "package" / "module"
        work.mkdir(parents=True)
        monkeypatch.chdir(work)
        assert PyprojectTomlConfigSettingsSource(FileSettings)() == {}

        class Configured(FileSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                pyproject_toml_depth=2
            )

        assert PyprojectTomlConfigSettingsSource(Configured)() == {"token": "table"}
        assert PyprojectTomlConfigSettingsSource(FileSettings, project)() == {
            "token": "table"
        }

        class Root(FileSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                pyproject_toml_table_header=()
            )

        assert PyprojectTomlConfigSettingsSource(Root, project)()["token"] == "root"
        local = work / "pyproject.toml"
        _ = local.write_text('[tool.pydantic-settings]\ntoken="nearest"')
        assert PyprojectTomlConfigSettingsSource(Configured)() == {"token": "nearest"}
        _ = local.write_text('[project]\nname="unrelated"')
        assert PyprojectTomlConfigSettingsSource(Configured)() == {}


class TestInitialSettingsSource:
    """Test constructor inputs and values from earlier sources."""

    def test_source_state_and_initial_aliases(self) -> None:
        """Expose earlier source values and prefer the first constructor alias."""

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

    def test_init_names_are_case_insensitive_only_at_top_level(self) -> None:
        """Match top-level input names without changing nested key case."""

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

    def test_init_unknown_names_remain_extra_inputs(self) -> None:
        """Preserve unknown constructor names for extra-field validation."""

        class Settings(BaseModel):
            model_config: ClassVar[ConfigDict] = {"extra": "forbid"}
            value: int = Field(alias="ALIAS")

        source = InitSettingsSource(Settings, {"ALIAS": 1, "value": 2})
        assert source() == {"ALIAS": 1, "value": 2}
        with pytest.raises(ValidationError, match="extra_forbidden"):
            _ = Settings.model_validate(source())
        assert InitSettingsSource(Settings, {"alias": 2, "ALIAS": 1})() == {"ALIAS": 2}


class TestDefaultSettingsSource:
    """Test partial updates to model and dataclass defaults."""

    def test_nested_default_partial_updates(self) -> None:
        """Copy nested defaults before merging partial updates."""

        class Settings(SourceSettings):
            connection: Connection = Connection(host="configured", port=9000)

        assert DefaultSettingsSource(Settings)() == {}
        defaults = DefaultSettingsSource(
            Settings, nested_model_default_partial_update=True
        )()
        assert defaults["connection"] == {
            "host": "configured",
            "port": 9000,
            "labels": [],
        }
        original = Connection(host="init")
        assert (
            InitSettingsSource(Settings, {"connection": original})()["connection"]
            is original
        )
        assert (
            InitSettingsSource(
                Settings,
                {"connection": original},
                nested_model_default_partial_update=True,
            )()["connection"]
            == original.model_dump()
        )
        assert (
            deep_merge(defaults, {"connection": {"port": 1234}})["connection"]["host"]
            == "configured"
        )
        assert defaults["connection"]["port"] == 9000

    def test_dataclass_default_partial_update(self) -> None:
        """Support dataclass defaults while preserving supplied dataclass instances."""

        @dataclasses.dataclass
        class Nested:
            port: int = 9100

        class Settings(BaseModel):
            nested: Nested = Field(default=Nested())

        source = DefaultSettingsSource(
            Settings, nested_model_default_partial_update=True
        )
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


class TestCustomSettingsSources:
    """Test custom decoding and source errors."""

    def test_custom_source_decoding_hook(self) -> None:
        """Let a custom source override value decoding."""

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

    def test_complex_value_decoding_hook_and_reread_after_errors(
        self, tmp_path: Path
    ) -> None:
        """Decode values with a custom hook and read the file again after errors."""

        class Settings(BaseModel):
            items: list[int] = []

        class CommaSeparatedSource(DotEnvSettingsSource):
            def decode_complex_value(
                self, field_name: str, field: FieldInfo, value: Any
            ) -> Any:
                return [int(item) for item in str(value).split(",")]

        dotenv = tmp_path / ".env"
        _ = dotenv.write_text("ITEMS=1,2")
        source = CommaSeparatedSource(Settings, env_file=dotenv)
        assert source() == {"items": [1, 2]}
        _ = dotenv.write_text("ITEMS=invalid")
        with pytest.raises(SettingsError, match="items"):
            _ = source()
        _ = dotenv.write_text("ITEMS=3,4")
        assert source() == {"items": [3, 4]}

    def test_source_read_failure_preserves_cause(self) -> None:
        """Keep the original read error as the cause of a settings error."""

        class FailingSource(EnvSettingsSource):
            def get_field_value(
                self, field: FieldInfo, field_name: str
            ) -> tuple[Any, str, bool]:
                raise OSError("cannot read backing store")

        with pytest.raises(SettingsError, match="connection") as error:
            _ = FailingSource(SourceSettings)()
        assert isinstance(error.value.__cause__, OSError)


class TestAsyncSourceLoading:
    """Test event loop responsiveness and cancellation when loading files."""

    @pytest.mark.anyio
    async def test_load_keeps_event_loop_responsive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Allow another task to run while a dotenv file read is blocked."""
        dotenv = tmp_path / ".env"
        _ = dotenv.write_text("COUNT=4\n")
        event_loop_thread = threading.get_ident()
        read_started = threading.Event()
        allow_read = threading.Event()
        read_text = Path.read_text

        def delayed_read(path: Path, *args: Any, **kwargs: Any) -> str:
            assert threading.get_ident() != event_loop_thread
            read_started.set()
            assert allow_read.wait(timeout=5), "The file read blocked the event loop"
            return read_text(path, *args, **kwargs)

        async def release_from_event_loop() -> None:
            assert await anyio.to_thread.run_sync(read_started.wait, 5)
            allow_read.set()

        monkeypatch.setattr(Path, "read_text", delayed_read)
        source = DotEnvSettingsSource(SourceSettings, env_file=dotenv)
        async with anyio.create_task_group() as task_group:
            _ = task_group.start_soon(release_from_event_loop)
            assert await source.load() == {"count": "4"}

    @pytest.mark.anyio
    async def test_load_matches_calling_the_source(self) -> None:
        """Return the same values as a direct call, including subclass overrides."""

        class DefaultingSource(SecretsSettingsSource):
            def __call__(self) -> dict[str, Any]:
                return {"token": "fallback", **super().__call__()}

        source = DefaultingSource(SourceSettings)
        assert await source.load() == source() == {"token": "fallback"}
        initial = InitSettingsSource(SourceSettings, {"count": 5})
        assert await initial.load() == initial() == {"count": 5}

    @pytest.mark.anyio
    @pytest.mark.parametrize("source_kind", ["dotenv", "secrets"])
    async def test_load_again_after_cancellation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_kind: str
    ) -> None:
        """Read current file contents after a cancelled load."""
        if source_kind == "dotenv":
            dotenv = tmp_path / ".env"
            _ = dotenv.write_text("COUNT=1")
            source = DotEnvSettingsSource(SourceSettings, env_file=dotenv)
            update = dotenv.write_text
            content = "COUNT=7"
        else:
            secret = tmp_path / "count"
            _ = secret.write_text("1")
            source = SecretsSettingsSource(SourceSettings, secrets_dir=tmp_path)
            update = secret.write_text
            content = "7"
        read_started = threading.Event()
        allow_read = threading.Event()
        read_text = Path.read_text

        def delayed_read(path: Path, *args: Any, **kwargs: Any) -> str:
            read_started.set()
            assert allow_read.wait(timeout=5)
            return read_text(path, *args, **kwargs)

        async def cancel_from_event_loop(scope: anyio.CancelScope) -> None:
            assert await anyio.to_thread.run_sync(read_started.wait, 5)
            scope.cancel()
            allow_read.set()

        scope = anyio.CancelScope()
        with monkeypatch.context() as patches:
            patches.setattr(Path, "read_text", delayed_read)
            async with anyio.create_task_group() as task_group:
                _ = task_group.start_soon(cancel_from_event_loop, scope)
                with scope:
                    _ = await source.load()
        assert scope.cancel_called
        _ = update(content)
        assert await source.load() == source() == {"count": "7"}
