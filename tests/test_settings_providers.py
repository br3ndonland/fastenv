"""Original provider tests using local fixtures and fake cloud clients."""

# SDK mocks intentionally expose dynamically typed attributes and callbacks.
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownLambdaType=false

from __future__ import annotations

import importlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any, ClassVar, cast
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field

from fastenv.settings.main import BaseSettings, SettingsConfigDict
from fastenv.settings.providers import (
    AWSSecretsManagerSettingsSource,
    AzureKeyVaultSettingsSource,
    GoogleSecretManagerSettingsSource,
    JsonConfigSettingsSource,
    NestedSecretsSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SecretVersion,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)
from fastenv.settings.sources import (
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
@pytest.mark.parametrize("format", ["json", "toml", "yaml"])
def test_config_files_merge_in_order(tmp_path: Path, format: str, deep: bool) -> None:
    contents = {
        "json": (
            '{"service":{"hostname":"first","port":9000}}',
            '{"service":{"port":9001}}',
        ),
        "toml": ('[service]\nhostname="first"\nport=9000', "[service]\nport=9001"),
        "yaml": (
            "service:\n  hostname: first\n  port: 9000\n",
            "service:\n  port: 9001\n",
        ),
    }
    source_class = {
        "json": JsonConfigSettingsSource,
        "toml": TomlConfigSettingsSource,
        "yaml": YamlConfigSettingsSource,
    }[format]
    files = [tmp_path / f"base.{format}", tmp_path / f"override.{format}"]
    for path, content in zip(files, contents[format]):
        _ = path.write_text(content)
    source = source_class(ProviderSettings, files, deep_merge=deep)
    expected: dict[str, dict[str, int | str]] = {"service": {"port": 9001}}
    if deep:
        expected["service"]["hostname"] = "first"
    assert source() == expected
    output = source()
    output["service"]["port"] = -1
    assert source() == expected


@pytest.mark.parametrize("format", ["json", "toml", "yaml"])
def test_config_file_model_config_and_disable(tmp_path: Path, format: str) -> None:
    source_class = {
        "json": JsonConfigSettingsSource,
        "toml": TomlConfigSettingsSource,
        "yaml": YamlConfigSettingsSource,
    }[format]
    path = tmp_path / f"config.{format}"
    _ = path.write_text(
        {
            "json": '{"token":"configured"}',
            "toml": 'token="configured"',
            "yaml": "token: configured",
        }[format]
    )

    class Configured(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            json_file=path if format == "json" else None,
            toml_file=path if format == "toml" else None,
            yaml_file=path if format == "yaml" else None,
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


@pytest.mark.parametrize("format,content", [("json", "5"), ("yaml", "- item")])
def test_config_rejects_non_mapping(tmp_path: Path, format: str, content: str) -> None:
    path = tmp_path / "config"
    _ = path.write_text(content)
    source_class = (
        JsonConfigSettingsSource if format == "json" else YamlConfigSettingsSource
    )
    with pytest.raises(SettingsError, match="mapping"):
        _ = source_class(ProviderSettings, path)


def test_file_resources_without_filesystem_paths(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("settings.json", '{"token":"resource"}')
    with zipfile.ZipFile(archive) as bundle:
        source = JsonConfigSettingsSource(
            ProviderSettings, zipfile.Path(bundle, "settings.json")
        )
        assert source() == {"token": "resource"}


def test_toml_and_yaml_table_selection(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    _ = toml.write_text('[app.runtime]\ntoken="selected"')
    yaml = tmp_path / "config.yaml"
    _ = yaml.write_text("runtime:\n  token: selected\n")

    class Configured(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            toml_file=toml,
            toml_table_header=("app", "runtime"),
            yaml_file=yaml,
            yaml_config_section="runtime",
        )

    assert TomlConfigSettingsSource(Configured)() == {"token": "selected"}
    assert YamlConfigSettingsSource(Configured)() == {"token": "selected"}
    with pytest.raises(KeyError):
        _ = TomlConfigSettingsSource(Configured, toml_table_header=("missing",))
    with pytest.raises(KeyError):
        _ = YamlConfigSettingsSource(Configured, yaml_config_section="missing")
    _ = yaml.write_text("")
    assert YamlConfigSettingsSource(ProviderSettings, yaml)() == {}


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


def test_optional_dependency_has_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unavailable(name: str) -> None:
        raise ImportError(name)

    monkeypatch.setattr(importlib, "import_module", unavailable)
    with pytest.raises(ImportError, match=r"fastenv\[aws\]"):
        _ = AWSSecretsManagerSettingsSource(ProviderSettings, "secret")
    path = tmp_path / "config.yaml"
    _ = path.write_text("token: value")
    with pytest.raises(ImportError, match=r"fastenv\[yaml\]"):
        _ = YamlConfigSettingsSource(ProviderSettings, path)


def test_aws_json_version_and_nested_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"token": "aws", "service--port": "9300", "unused": "ignored"}
        )
    }
    module = SimpleNamespace(client=Mock(return_value=client))
    monkeypatch.setattr(importlib, "import_module", Mock(return_value=module))
    source = AWSSecretsManagerSettingsSource(
        ProviderSettings, "app/settings", region_name="us-east-2", version_id="pinned"
    )
    assert source() == {"token": "aws", "service": {"port": "9300"}}
    client.get_secret_value.assert_called_once_with(
        SecretId="app/settings", VersionId="pinned"
    )
    module.client.assert_called_once_with(
        "secretsmanager", region_name="us-east-2", endpoint_url=None
    )


@pytest.mark.parametrize(
    "response", [{"SecretBinary": b"binary"}, {"SecretString": "[]"}]
)
def test_aws_rejects_non_object_secrets(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, str | bytes]
) -> None:
    client = Mock()
    client.get_secret_value.return_value = response
    monkeypatch.setattr(
        importlib,
        "import_module",
        Mock(return_value=SimpleNamespace(client=Mock(return_value=client))),
    )
    with pytest.raises(SettingsError, match="JSON object"):
        _ = AWSSecretsManagerSettingsSource(ProviderSettings, "app/settings")


def test_azure_only_fetches_matching_enabled_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.list_properties_of_secrets.return_value = [
        SimpleNamespace(name="token", enabled=True),
        SimpleNamespace(name="service--port", enabled=True),
        SimpleNamespace(name="unused", enabled=True),
        SimpleNamespace(name="disabled", enabled=False),
    ]
    client.get_secret.side_effect = lambda name: SimpleNamespace(
        value={"token": "azure", "service--port": "9400"}[name]
    )
    factory = Mock(return_value=client)
    monkeypatch.setattr(
        importlib,
        "import_module",
        Mock(return_value=SimpleNamespace(SecretClient=factory)),
    )
    credential = object()
    source = AzureKeyVaultSettingsSource(
        ProviderSettings, "https://vault.example", credential
    )
    assert source() == {"token": "azure", "service": {"port": "9400"}}
    assert client.get_secret.call_count == 2
    factory.assert_called_once_with(
        vault_url="https://vault.example", credential=credential
    )


def test_azure_name_conversion_preserves_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Configured(BaseSettings):
        access_key: str
        alias_value: str = Field(alias="Custom-Alias")

    client = Mock()
    client.list_properties_of_secrets.return_value = [
        SimpleNamespace(name=name) for name in ["access-key", "Custom-Alias"]
    ]
    client.get_secret.side_effect = lambda name: SimpleNamespace(value=name)
    monkeypatch.setattr(
        importlib,
        "import_module",
        Mock(return_value=SimpleNamespace(SecretClient=Mock(return_value=client))),
    )
    source = AzureKeyVaultSettingsSource(
        Configured, "url", object(), dash_to_underscore=True
    )
    assert source() == {"access_key": "access-key", "Custom-Alias": "Custom-Alias"}

    class SnakeSettings(BaseSettings):
        api_key: str
        service: Service

    client.list_properties_of_secrets.return_value = [
        SimpleNamespace(name=name) for name in ["APIKey", "Service--Port"]
    ]
    client.get_secret.side_effect = lambda name: SimpleNamespace(
        value="9500" if "Port" in name else "value"
    )
    source = AzureKeyVaultSettingsSource(
        SnakeSettings, "url", object(), snake_case_conversion=True
    )
    assert source() == {"api_key": "value", "service": {"port": "9500"}}


def test_google_uses_previous_source_project_and_only_matching_secrets() -> None:
    client = Mock()
    client.list_secrets.return_value = [
        SimpleNamespace(name=f"projects/runtime/secrets/{name}")
        for name in ["token", "service__port", "unused"]
    ]
    client.access_secret_version.side_effect = lambda request: SimpleNamespace(
        payload=SimpleNamespace(
            data=b"9600" if "port" in request["name"] else b"google"
        )
    )

    class Configured(ProviderSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_nested_delimiter="__"
        )

    source = GoogleSecretManagerSettingsSource(
        Configured, secret_client=client, project_id_field="deployment_project"
    )
    client.list_secrets.assert_not_called()
    source._set_current_state({"deployment_project": "runtime"})  # pyright: ignore[reportPrivateUsage]
    assert source() == {"token": "google", "service": {"port": "9600"}}
    client.list_secrets.assert_called_once_with(request={"parent": "projects/runtime"})
    assert client.access_secret_version.call_count == 2


def test_google_default_credentials_and_explicit_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.list_secrets.return_value = []
    credential = object()
    auth = SimpleNamespace(default=Mock(return_value=(credential, "default-project")))
    factory = Mock(return_value=client)

    def lookup_module(name: str) -> Any:
        return (
            auth
            if name == "google.auth"
            else SimpleNamespace(SecretManagerServiceClient=factory)
        )

    monkeypatch.setattr(importlib, "import_module", lookup_module)
    source = GoogleSecretManagerSettingsSource(
        ProviderSettings, project_id="explicit-project"
    )
    source._set_current_state({"project_id": "earlier-project"})  # pyright: ignore[reportPrivateUsage]
    assert source() == {}
    factory.assert_called_once_with(credentials=credential)
    client.list_secrets.assert_called_once_with(
        request={"parent": "projects/explicit-project"}
    )
    auth.default.return_value = (credential, None)
    with pytest.raises(SettingsError, match="project_id"):
        _ = GoogleSecretManagerSettingsSource(ProviderSettings)()


def test_file_section_must_be_mapping(tmp_path: Path) -> None:
    path = tmp_path / "invalid.toml"
    _ = path.write_text('section="scalar"')
    with pytest.raises(SettingsError, match="mapping"):
        _ = TomlConfigSettingsSource(
            ProviderSettings, path, toml_table_header=("section", "nested")
        )
    yaml = tmp_path / "invalid.yaml"
    _ = yaml.write_text("- list-item")
    with pytest.raises(TypeError, match="mapping"):
        _ = YamlConfigSettingsSource(
            ProviderSettings, yaml, yaml_config_section="section"
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


def test_google_versions_nested_metadata_and_cache() -> None:
    class Nested(BaseModel):
        pinned: Annotated[str, SecretVersion("7")]

    class Versioned(BaseSettings):
        token: str = Field(default="", alias="access-token")
        previous: Annotated[str, SecretVersion("3")] = Field(
            default="", alias="access-token"
        )
        same_version: Annotated[str, SecretVersion("3")] = Field(
            default="", alias="access-token"
        )
        nested: Nested
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            populate_by_name=True, env_nested_delimiter="__"
        )

    client = Mock()
    client.list_secrets.return_value = [
        SimpleNamespace(name=f"projects/p/secrets/{name}")
        for name in ["access-token", "nested__pinned"]
    ]

    def access_version(request: dict[str, str]) -> SimpleNamespace:
        return SimpleNamespace(
            payload=SimpleNamespace(data=request["name"].rsplit("/", 1)[-1].encode())
        )

    client.access_secret_version.side_effect = access_version
    source = GoogleSecretManagerSettingsSource(
        Versioned, project_id="p", secret_client=client
    )
    data = source()
    assert data == {
        "token": "latest",
        "previous": "3",
        "same_version": "3",
        "nested": {"pinned": "7"},
    }
    assert client.access_secret_version.call_count == 3


def test_google_case_insensitive_prefers_exact_names() -> None:
    class Cases(BaseSettings):
        api_key: str
        custom: str = Field(alias="PascalName")
        fallback: str

    client = Mock()
    client.list_secrets.return_value = [
        SimpleNamespace(name=f"projects/p/secrets/{name}")
        for name in ["api_key", "API_KEY", "pascalname", "PascalName", "FALLBACK"]
    ]

    def access_version(request: dict[str, str]) -> SimpleNamespace:
        return SimpleNamespace(
            payload=SimpleNamespace(data=request["name"].split("/")[-3].encode())
        )

    client.access_secret_version.side_effect = access_version
    source = GoogleSecretManagerSettingsSource(
        Cases, project_id="p", secret_client=client, case_sensitive=False
    )
    assert source() == {
        "api_key": "api_key",
        "PascalName": "PascalName",
        "fallback": "FALLBACK",
    }


def test_yaml_nested_sections_and_literal_dot_precedence(tmp_path: Path) -> None:
    yaml = tmp_path / "nested.yaml"
    _ = yaml.write_text("outer:\n  inner:\n    token: nested\n")
    assert YamlConfigSettingsSource(
        ProviderSettings, yaml, yaml_config_section="outer.inner"
    )() == {"token": "nested"}
    with pytest.raises(ValueError, match="empty"):
        _ = YamlConfigSettingsSource(ProviderSettings, yaml, yaml_config_section="")
    with pytest.raises(TypeError, match="mapping"):
        _ = YamlConfigSettingsSource(
            ProviderSettings, yaml, yaml_config_section="outer.inner.token"
        )
    _ = yaml.write_text(
        "outer.inner:\n  token: literal\nouter:\n  inner:\n    token: nested\n"
    )
    assert YamlConfigSettingsSource(
        ProviderSettings, yaml, yaml_config_section="outer.inner"
    )() == {"token": "literal"}
