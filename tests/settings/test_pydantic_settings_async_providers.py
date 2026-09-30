# Settings dictionaries and patched filesystem methods are dynamic boundaries.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import threading
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import anyio
import pytest
from pydantic import BaseModel

from fastenv import BaseSettings, SettingsConfigDict
from fastenv.settings.pydantic_settings_providers import (
    JsonConfigSettingsSource,
    NestedSecretsSettingsSource,
    PyprojectTomlConfigSettingsSource,
    TomlConfigSettingsSource,
)
from fastenv.settings.pydantic_settings_sources import (
    DEFER_SETTINGS_IO,
    PydanticBaseSettingsSource,
    SettingsError,
)

pytestmark = pytest.mark.anyio


class Service(BaseModel):
    hostname: str = "localhost"
    port: int = 8000


class ProviderSettings(BaseSettings):
    service: Service = Service()
    token: str = "default"


def _deferred(
    factory: Callable[[], PydanticBaseSettingsSource],
) -> PydanticBaseSettingsSource:
    token = DEFER_SETTINGS_IO.set(True)
    try:
        return factory()
    finally:
        DEFER_SETTINGS_IO.reset(token)


def _guard_filesystem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow filesystem calls only in AnyIO workers, including during setup."""
    # Import AnyIO's file helpers before guarding reads from settings sources.
    _ = anyio.Path
    event_loop_thread = threading.get_ident()

    def guarded(method: Callable[..., Any]) -> Callable[..., Any]:
        def check(*args: Any, **kwargs: Any) -> Any:
            assert threading.get_ident() != event_loop_thread
            return method(*args, **kwargs)

        return check

    for method_name in (
        "cwd",
        "expanduser",
        "exists",
        "is_dir",
        "is_file",
        "open",
        "read_text",
        "stat",
    ):
        method = getattr(Path, method_name)
        monkeypatch.setattr(Path, method_name, guarded(method))


class TestAsyncConfigFiles:
    """Test asynchronous JSON, TOML, and package resource loading."""

    @pytest.mark.parametrize("deep", [False, True])
    @pytest.mark.parametrize("format", ["json", "toml"])
    async def test_async_config_order_and_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, format: str, deep: bool
    ) -> None:
        """Merge files in order and return values that callers can change safely."""
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
        files = [tmp_path / f"base.{format}", tmp_path / f"override.{format}"]
        for path, content in zip(files, contents[format]):
            _ = path.write_text(content)
        source_class = {
            "json": JsonConfigSettingsSource,
            "toml": TomlConfigSettingsSource,
        }[format]
        with monkeypatch.context() as guarded:
            _guard_filesystem(guarded)
            source = _deferred(
                lambda: source_class(
                    ProviderSettings,
                    [tmp_path / "missing", files[0], tmp_path, files[1]],
                    deep_merge=deep,
                )
            )
            output = await source.load()
        expected_service: dict[str, int | str] = {"port": 9001}
        if deep:
            expected_service["hostname"] = "first"
        assert output == {"token": "base", "service": expected_service}
        output["service"]["port"] = -1
        assert source()["service"] == expected_service

    async def test_async_json_encoding_and_call_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Honor JSON file encoding and a custom source call method."""
        path = tmp_path / "config.json"
        _ = path.write_bytes('{"token":"caf\\u00e9"}'.encode("utf-16"))

        class Customized(JsonConfigSettingsSource):
            def __call__(self) -> dict[str, Any]:
                return {"token": super().__call__()["token"].upper()}

        with monkeypatch.context() as guarded:
            _guard_filesystem(guarded)
            source = _deferred(
                lambda: Customized(ProviderSettings, path, json_file_encoding="utf-16")
            )
            assert await source.load() == {"token": "CAF\u00c9"}

    async def test_async_resource_reads_use_worker_thread(self, tmp_path: Path) -> None:
        """Read package resources outside the event-loop thread."""
        archive = tmp_path / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("settings.json", '{"token":"resource"}')
        event_loop_thread = threading.get_ident()

        class Resource(zipfile.Path):
            def is_file(self) -> bool:
                assert threading.get_ident() != event_loop_thread
                return super().is_file()

            def read_text(self, *args: Any, **kwargs: Any) -> str:
                assert threading.get_ident() != event_loop_thread
                return super().read_text(*args, **kwargs)

        with zipfile.ZipFile(archive) as bundle:
            source = _deferred(
                lambda: JsonConfigSettingsSource(
                    ProviderSettings,
                    [
                        Resource(bundle, "missing.json"),
                        Resource(bundle, "settings.json"),
                    ],
                )
            )
            assert await source.load() == {"token": "resource"}

    @pytest.mark.parametrize(
        "source_class", [JsonConfigSettingsSource, TomlConfigSettingsSource]
    )
    async def test_async_disabled_configuration_files(
        self,
        source_class: type[JsonConfigSettingsSource | TomlConfigSettingsSource],
    ) -> None:
        """Return no values when configuration files are disabled."""
        assert (
            await _deferred(lambda: source_class(ProviderSettings, None)).load() == {}
        )

    @pytest.mark.parametrize(
        ("source_class", "contents", "error"),
        [
            (JsonConfigSettingsSource, "[1]", SettingsError),
            (JsonConfigSettingsSource, "{", json.JSONDecodeError),
            (TomlConfigSettingsSource, "[", tomllib.TOMLDecodeError),
        ],
    )
    async def test_async_invalid_configuration(
        self,
        tmp_path: Path,
        source_class: type[JsonConfigSettingsSource | TomlConfigSettingsSource],
        contents: str,
        error: type[Exception],
    ) -> None:
        """Raise the expected error for invalid configuration file contents."""
        path = tmp_path / "invalid"
        _ = path.write_text(contents)
        source = _deferred(lambda: source_class(ProviderSettings, path))
        with pytest.raises(error):
            _ = await source.load()

    @pytest.mark.parametrize(
        "header", [("app", "runtime"), ("missing",), ("scalar", "nested")]
    )
    async def test_async_toml_table_selection(
        self, tmp_path: Path, header: tuple[str, ...]
    ) -> None:
        """Read the selected TOML table and reject missing or non-table values."""
        path = tmp_path / "config.toml"
        _ = path.write_text('scalar="value"\n[app.runtime]\ntoken="selected"')
        source = _deferred(
            lambda: TomlConfigSettingsSource(
                ProviderSettings, path, toml_table_header=header
            )
        )
        if header == ("missing",):
            with pytest.raises(KeyError):
                _ = await source.load()
        elif header == ("scalar", "nested"):
            with pytest.raises(SettingsError, match="mapping"):
                _ = await source.load()
        else:
            assert await source.load() == {"token": "selected"}

    async def test_async_pyproject_discovery_and_table_selection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Find nearby pyproject files within the configured search depth."""
        project = tmp_path / "pyproject.toml"
        _ = project.write_text('token="root"\n[tool.pydantic-settings]\ntoken="parent"')
        work = tmp_path / "package" / "module"
        work.mkdir(parents=True)
        monkeypatch.chdir(work)

        class ParentSettings(ProviderSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                pyproject_toml_depth=2
            )

        class RootSettings(ProviderSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                pyproject_toml_table_header=()
            )

        with monkeypatch.context() as guarded:
            _guard_filesystem(guarded)
            limited = _deferred(
                lambda: PyprojectTomlConfigSettingsSource(ProviderSettings)
            )
            parent = _deferred(
                lambda: PyprojectTomlConfigSettingsSource(ParentSettings)
            )
            root = _deferred(
                lambda: PyprojectTomlConfigSettingsSource(RootSettings, project)
            )
            assert await limited.load() == {}
            assert await parent.load() == {"token": "parent"}
            assert (await root.load())["token"] == "root"
        local = work / "pyproject.toml"
        _ = local.write_text('[tool.pydantic-settings]\ntoken="nearest"')
        assert await parent.load() == {"token": "nearest"}
        _ = local.write_text('[project]\nname="unrelated"')
        assert await parent.load() == {}


class TestAsyncNestedSecrets:
    """Test asynchronous loading of nested secret files."""

    async def test_async_nested_secret_order_subdirectories_and_environment_isolation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Apply secret directory priority without falling back to environment values."""
        first, last = tmp_path / "first", tmp_path / "last"
        (first / "service").mkdir(parents=True)
        (last / "service").mkdir(parents=True)
        _ = (first / "service" / "port").write_text("9000\n")
        _ = (first / "service" / "hostname").write_text("secrets\n")
        _ = (last / "service" / "port").write_text("9001\n")
        _ = (last / "TOKEN").write_text("upper")
        _ = (last / "token").write_text("lower")
        monkeypatch.setenv("TOKEN", "must-not-load")
        with monkeypatch.context() as guarded:
            _guard_filesystem(guarded)
            source = _deferred(
                lambda: NestedSecretsSettingsSource(
                    ProviderSettings,
                    secrets_dir=[first, last],
                    secrets_nested_subdir=True,
                )
            )
            assert await source.load() == {
                "service": {"hostname": "secrets", "port": "9001"},
                "token": "lower",
            }

    async def test_async_nested_secret_prefix_case_and_delimiter(
        self, tmp_path: Path
    ) -> None:
        """Match secret prefixes, letter case, and nested field separators."""
        _ = (tmp_path / "APP_TOKEN").write_text("secret")
        _ = (tmp_path / "APP_service_port").write_text("9002")
        source = _deferred(
            lambda: NestedSecretsSettingsSource(
                ProviderSettings,
                secrets_dir=tmp_path,
                secrets_prefix="APP_",
                secrets_case_sensitive=True,
                secrets_nested_delimiter="_",
            )
        )
        assert await source.load() == {"service": {"port": "9002"}}
        assert (
            await _deferred(
                lambda: NestedSecretsSettingsSource(ProviderSettings)
            ).load()
            == {}
        )

    @pytest.mark.parametrize("policy", ["ok", "warn", "error"])
    async def test_async_nested_secret_missing_directory(
        self, tmp_path: Path, policy: Any
    ) -> None:
        """Ignore, warn about, or reject missing secret directories as configured."""
        source = _deferred(
            lambda: NestedSecretsSettingsSource(
                ProviderSettings,
                secrets_dir=tmp_path / "missing",
                secrets_dir_missing=policy,
            )
        )
        if policy == "error":
            with pytest.raises(SettingsError, match="does not exist"):
                _ = await source.load()
        elif policy == "warn":
            with pytest.warns(UserWarning, match="does not exist"):
                assert await source.load() == {}
        else:
            assert await source.load() == {}

    async def test_async_nested_secret_invalid_directory_and_size_limit(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject non-directory secret paths and files exceeding the size limit."""
        path = tmp_path / "token"
        _ = path.write_text("large")
        invalid_directory = _deferred(
            lambda: NestedSecretsSettingsSource(ProviderSettings, secrets_dir=path)
        )
        with pytest.raises(SettingsError, match="not a directory"):
            _ = await invalid_directory.load()
        oversized = _deferred(
            lambda: NestedSecretsSettingsSource(
                ProviderSettings, secrets_dir=tmp_path, secrets_dir_max_size=4
            )
        )
        with pytest.raises(SettingsError, match="maximum size"):
            _ = await oversized.load()

    @pytest.mark.parametrize("asynchronous", [False, True])
    async def test_nested_secret_size_limit_handles_cumulative_file_growth(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asynchronous: bool
    ) -> None:
        """Enforce the combined size limit when secret files grow while being read."""
        for name in ("a", "b"):
            _ = (tmp_path / name).write_text("x")
        original_open = Path.open

        def grow_before_read(path: Path, mode: str, *args: Any, **kwargs: Any):
            if path.parent == tmp_path and mode == "rb":
                with original_open(path, "w") as stream:
                    _ = stream.write("grown")
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "open", grow_before_read)
        with pytest.raises(SettingsError, match="maximum size"):
            if asynchronous:
                source = _deferred(
                    lambda: NestedSecretsSettingsSource(
                        ProviderSettings, secrets_dir=tmp_path, secrets_dir_max_size=8
                    )
                )
                _ = await source.load()
            else:
                _ = NestedSecretsSettingsSource(
                    ProviderSettings, secrets_dir=tmp_path, secrets_dir_max_size=8
                )
