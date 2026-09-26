# File sources expose dynamic values and configurable Pydantic model fields.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, ClassVar, cast

import pytest
from pydantic import BaseModel, Field

from fastenv.settings.pydantic_settings import BaseSettings, SettingsConfigDict
from fastenv.settings.pydantic_settings_providers import (
    JsonConfigSettingsSource,
    NestedSecretsSettingsSource,
    PyprojectTomlConfigSettingsSource,
    TomlConfigSettingsSource,
)
from fastenv.settings.pydantic_settings_sources import (
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsError,
)


class Service(BaseModel):
    hostname: str = "localhost"
    port: int = 8000


class ProviderSettings(BaseSettings):
    service: Service = Service()
    token: str = "default"


@pytest.mark.parametrize("deep", [False, True])
@pytest.mark.parametrize("format", ["json", "toml"])
def test_config_files_merge_in_order(tmp_path: Path, format: str, deep: bool) -> None:
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
    source = source_class(ProviderSettings, files, deep_merge=deep)
    expected_service: dict[str, int | str] = {"port": 9001}
    if deep:
        expected_service["hostname"] = "first"
    expected = {"token": "base", "service": expected_service}
    assert source() == expected
    output = source()
    output["service"]["port"] = -1
    assert source() == expected


@pytest.mark.parametrize("format", ["json", "toml"])
def test_config_file_model_config_and_disable(tmp_path: Path, format: str) -> None:
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

    class Configured(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            json_file=path if format == "json" else None,
            toml_file=path if format == "toml" else None,
        )

    assert source_class(Configured)() == {"token": "configured"}
    assert source_class(Configured, None)() == {}
    assert source_class(Configured, tmp_path / "missing")() == {}
    assert source_class(Configured, tmp_path)() == {}


def test_json_encoding_alias_and_settings_integration(tmp_path: Path) -> None:
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


def test_json_config_rejects_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "config"
    _ = path.write_text("5")
    with pytest.raises(SettingsError, match="mapping"):
        _ = JsonConfigSettingsSource(ProviderSettings, path)


def test_file_resources_without_filesystem_paths(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("settings.json", '{"token":"resource"}')
    with zipfile.ZipFile(archive) as bundle:
        source = JsonConfigSettingsSource(
            ProviderSettings, zipfile.Path(bundle, "settings.json")
        )
        assert source() == {"token": "resource"}


def test_toml_table_selection(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    _ = toml.write_text('[app.runtime]\ntoken="selected"')

    class Configured(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            toml_file=toml,
            toml_table_header=("app", "runtime"),
        )

    assert TomlConfigSettingsSource(Configured)() == {"token": "selected"}
    with pytest.raises(KeyError):
        _ = TomlConfigSettingsSource(Configured, toml_table_header=("missing",))


def test_pyproject_search_depth_explicit_file_and_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "pyproject.toml"
    _ = project.write_text('token="root"\n[tool.pydantic-settings]\ntoken="table"')
    work = tmp_path / "package" / "module"
    work.mkdir(parents=True)
    monkeypatch.chdir(work)
    assert PyprojectTomlConfigSettingsSource(ProviderSettings)() == {}

    class Configured(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            pyproject_toml_depth=2
        )

    assert PyprojectTomlConfigSettingsSource(Configured)() == {"token": "table"}
    assert PyprojectTomlConfigSettingsSource(ProviderSettings, project)() == {
        "token": "table"
    }

    class Root(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            pyproject_toml_table_header=()
        )

    assert PyprojectTomlConfigSettingsSource(Root, project)()["token"] == "root"
    local = work / "pyproject.toml"
    _ = local.write_text('[tool.pydantic-settings]\ntoken="nearest"')
    assert PyprojectTomlConfigSettingsSource(Configured)() == {"token": "nearest"}
    _ = local.write_text('[project]\nname="unrelated"')
    assert PyprojectTomlConfigSettingsSource(Configured)() == {}


def test_nested_secrets_overrides_and_no_environment_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, last = tmp_path / "first", tmp_path / "last"
    first.mkdir()
    last.mkdir()
    _ = (first / "APP_SERVICE__PORT").write_text("9000\n")
    _ = (first / "APP_SERVICE__HOSTNAME").write_text("secrets\n")
    _ = (last / "APP_SERVICE__PORT").write_text("9001\n")
    monkeypatch.setenv("APP_TOKEN", "must-not-load")

    class Configured(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="APP_", env_nested_delimiter="__", secrets_dir=[first, last]
        )

    source = NestedSecretsSettingsSource(SecretsSettingsSource(Configured))
    assert source() == {"service": {"hostname": "secrets", "port": "9001"}}
    assert (
        NestedSecretsSettingsSource(Configured, secrets_dir=first)()["service"]["port"]
        == "9000"
    )


def test_nested_secret_subdirectories_and_config_overrides(tmp_path: Path) -> None:
    service = tmp_path / "service"
    service.mkdir()
    _ = (service / "port").write_text("9100")
    _ = (tmp_path / "token").write_text("secret")

    class Configured(ProviderSettings):
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


def test_nested_secret_case_sensitivity_and_delimiter(tmp_path: Path) -> None:
    _ = (tmp_path / "TOKEN").write_text("upper")
    _ = (tmp_path / "service_port").write_text("9200")
    source = NestedSecretsSettingsSource(
        ProviderSettings,
        secrets_dir=tmp_path,
        secrets_nested_delimiter="_",
        secrets_case_sensitive=True,
    )
    assert source() == {"service": {"port": "9200"}}
    assert (
        NestedSecretsSettingsSource(
            ProviderSettings, secrets_dir=tmp_path, secrets_case_sensitive=False
        )()["token"]
        == "upper"
    )


def test_nested_secret_missing_and_size_limits(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert NestedSecretsSettingsSource(ProviderSettings)() == {}
    assert (
        NestedSecretsSettingsSource(
            ProviderSettings, secrets_dir=missing, secrets_dir_missing="ok"
        )()
        == {}
    )
    with pytest.warns(UserWarning, match="does not exist"):
        _ = NestedSecretsSettingsSource(ProviderSettings, secrets_dir=missing)
    with pytest.raises(SettingsError, match="does not exist"):
        _ = NestedSecretsSettingsSource(
            ProviderSettings, secrets_dir=missing, secrets_dir_missing="error"
        )
    secret = tmp_path / "token"
    _ = secret.write_text("large")
    with pytest.raises(SettingsError, match="maximum size"):
        _ = NestedSecretsSettingsSource(
            ProviderSettings, secrets_dir=tmp_path, secrets_dir_max_size=4
        )
    with pytest.raises(SettingsError, match="not a directory"):
        _ = NestedSecretsSettingsSource(ProviderSettings, secrets_dir=secret)


def test_file_section_must_be_mapping(tmp_path: Path) -> None:
    path = tmp_path / "invalid.toml"
    _ = path.write_text('section="scalar"')
    with pytest.raises(SettingsError, match="mapping"):
        _ = TomlConfigSettingsSource(
            ProviderSettings, path, toml_table_header=("section", "nested")
        )


def test_nested_secret_rejects_invalid_missing_directory_policy() -> None:
    class Invalid(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict()

    cast(Any, Invalid.model_config)["secrets_dir_missing"] = "ignore-typo"
    with pytest.raises(SettingsError, match="secrets_dir_missing"):
        _ = NestedSecretsSettingsSource(Invalid)


def test_nested_secret_size_limit_handles_file_growth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / "token"
    _ = secret.write_text("small")
    original_open = Path.open

    def grow_before_read(path: Path, mode: str, *args: Any, **kwargs: Any):
        if path == secret and mode == "rb":
            with original_open(path, "w") as stream:
                _ = stream.write("newly grown content exceeds the limit")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_before_read)
    with pytest.raises(SettingsError, match="maximum size"):
        _ = NestedSecretsSettingsSource(
            ProviderSettings, secrets_dir=tmp_path, secrets_dir_max_size=8
        )
