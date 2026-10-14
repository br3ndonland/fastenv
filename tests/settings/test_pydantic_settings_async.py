# Settings sources expose unvalidated values and constructor configuration.
# pyright: reportCallIssue=false, reportAny=false, reportExplicitAny=false

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any, ClassVar, Self

import anyio
import pytest
from pydantic import AliasChoices, BaseModel, Field, ValidationError, model_validator
from pydantic.fields import FieldInfo

from fastenv import BaseSettings, SettingsConfigDict, SettingsError
from fastenv.settings.pydantic_settings import SettingsSource
from fastenv.settings.pydantic_settings_sources import (
    DEFER_SETTINGS_IO,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
)

pytestmark = pytest.mark.anyio


class TestAsyncSettingsLoading:
    """Test asynchronous loading, validation, and constructor options."""

    async def test_async_source_precedence_and_overrides(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Apply the same source priority to asynchronous and synchronous loads."""
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("FASTENV_ASYNC_PRIORITY=dotenv\n")
        secrets = tmp_path / "secrets"
        secrets.mkdir()
        _ = (secrets / "FASTENV_ASYNC_PRIORITY").write_text("secret\n")

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_prefix="FASTENV_ASYNC_", env_file=dotenv, secrets_dir=secrets
            )
            priority: str = "default"

        monkeypatch.setenv("FASTENV_ASYNC_PRIORITY", "environment")
        assert (await Settings.load(priority="init")).priority == "init"
        assert (await Settings.load()).priority == "environment"
        monkeypatch.delenv("FASTENV_ASYNC_PRIORITY")
        assert (await Settings.load()).priority == "dotenv"
        assert (await Settings.load(_env_file=None)).priority == "secret"
        assert (
            await Settings.load(_env_file=None, _secrets_dir=[])
        ).priority == "default"
        assert "FASTENV_ASYNC_PRIORITY" not in os.environ

    async def test_async_constructor_options_and_aliases(self, tmp_path: Path) -> None:
        """Honor aliases and constructor overrides during asynchronous loading."""

        class Database(BaseModel):
            host: str = "default"
            port: int = 8000

        class Settings(BaseSettings):
            database: Database = Field(
                default=Database(host="configured"),
                validation_alias=AliasChoices("DATABASE", "database"),
            )
            value: str | None = "fallback"
            empty: str = "default"

        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text(
            "APP_DATABASE__port=9000\nAPP_value=none\nAPP_empty=\n", encoding="utf-16"
        )
        options: dict[str, Any] = {
            "_case_sensitive": True,
            "_env_prefix": "APP_",
            "_env_prefix_target": "all",
            "_env_nested_delimiter": "__",
            "_env_nested_max_split": 1,
            "_env_file": dotenv,
            "_env_file_encoding": "utf-16",
            "_env_parse_none_str": "none",
            "_env_ignore_empty": True,
            "_env_parse_enums": True,
            "_nested_model_default_partial_update": True,
        }
        settings = await Settings.load(**options)
        assert settings.model_dump() == {
            "database": {"host": "configured", "port": 9000},
            "value": None,
            "empty": "default",
        }
        assert settings.model_dump() == Settings(**options).model_dump()
        assert settings.model_fields_set == {"database", "value"}
        unchanged = await Settings.load(_nested_model_default_partial_update=True)
        assert unchanged.model_fields_set == set()

    async def test_async_load_reads_and_validates_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read the file once, then construct and validate the model once."""
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("FASTENV_ASYNC_COUNT=7")
        calls: list[str] = []
        original = DotEnvSettingsSource.load

        async def load(source: DotEnvSettingsSource) -> dict[str, Any]:
            calls.append("read")
            result = await original(source)
            _ = dotenv.write_text("FASTENV_ASYNC_COUNT=invalid")
            return result

        monkeypatch.setattr(DotEnvSettingsSource, "load", load)

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_file=dotenv, env_prefix="FASTENV_ASYNC_"
            )
            count: int

            def __init__(self, **values: Any) -> None:
                assert not DEFER_SETTINGS_IO.get()
                calls.append("construct")
                super().__init__(**values)

            @model_validator(mode="after")
            def record_validation(self) -> Self:
                assert not DEFER_SETTINGS_IO.get()
                calls.append("validate")
                return self

        settings = await Settings.load()
        assert isinstance(settings, Settings)
        assert settings.count == 7
        assert calls == ["read", "construct", "validate"]

    async def test_async_no_sources_and_validation_errors(self) -> None:
        """Use defaults without sources and report invalid values during async loading."""

        class Settings(BaseSettings):
            count: int = 1

            @classmethod
            def settings_customise_sources(
                cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
            ) -> tuple[SettingsSource, ...]:
                return ()

        assert (await Settings.load(count=9)).count == 1
        assert (await Settings.load()).model_fields_set == set()

        class Invalid(BaseSettings):
            count: int

        with pytest.raises(ValidationError):
            _ = await Invalid.load(count="invalid")
        assert not DEFER_SETTINGS_IO.get()

    async def test_async_fields_do_not_collide_with_factory_parameters(self) -> None:
        """Allow a field named cls when loading settings asynchronously."""

        class Settings(BaseSettings):
            cls: str

        assert (await Settings.load(cls="value")).cls == "value"

    @pytest.mark.parametrize("coroutine", [False, True])
    async def test_sync_constructor_rejects_async_sources(
        self, coroutine: bool
    ) -> None:
        """Require Settings.load() when a source returns an awaitable."""

        class Deferred:
            def __await__(self) -> Generator[None, None, dict[str, Any]]:
                yield
                return {"value": "deferred"}

        async def source() -> dict[str, Any]:
            return {"value": "async"}

        class Settings(BaseSettings):
            value: str

            @classmethod
            def settings_customise_sources(
                cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
            ) -> tuple[SettingsSource, ...]:
                return (source if coroutine else Deferred,)

        with pytest.raises(SettingsError, match="await Settings.load"):
            _ = Settings()
        assert (await Settings.load()).value == ("async" if coroutine else "deferred")


class TestAsyncSettingsSources:
    """Test custom sources used during asynchronous loading."""

    async def test_custom_sync_and_async_sources_share_prior_state(self) -> None:
        """Run custom sources in order and expose values from earlier sources."""
        events: list[str] = []

        async def remote() -> dict[str, Any]:
            assert not DEFER_SETTINGS_IO.get()
            events.append("remote-start")
            await anyio.lowlevel.checkpoint()
            events.append("remote-end")
            return {"alternate": 20, "remote": True}

        class Computed(PydanticBaseSettingsSource):
            def get_field_value(
                self, field: FieldInfo, field_name: str
            ) -> tuple[Any, str, bool]:
                return None, field_name, False

            def __call__(self) -> dict[str, Any]:
                assert events == ["remote-start", "remote-end"]
                assert self.current_state == {"count": 2, "remote": True}
                assert self.settings_sources_data["remote"] == {
                    "alternate": 20,
                    "remote": True,
                }
                events.append("computed")
                return {"double": self.current_state["count"] * 2}

        class AsyncComputed(Computed):
            async def load(self) -> dict[str, Any]:
                assert events[-1] == "computed"
                assert self.current_state["double"] == 4
                assert self.settings_sources_data["Computed"] == {"double": 4}
                await anyio.lowlevel.checkpoint()
                events.append("async-computed")
                return {"last": "async"}

        class Settings(BaseSettings):
            count: int = Field(validation_alias=AliasChoices("count", "alternate"))
            double: int
            remote: bool
            last: str

            @classmethod
            def settings_customise_sources(
                cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
            ) -> tuple[SettingsSource, ...]:
                assert DEFER_SETTINGS_IO.get()
                computed = Computed(settings_cls)
                assert computed.get_field_value(
                    settings_cls.model_fields["count"], "count"
                ) == (None, "count", False)
                return (
                    sources["init_settings"],
                    remote,
                    computed,
                    AsyncComputed(settings_cls),
                )

        settings = await Settings.load(alternate=2)
        assert settings.model_dump() == {
            "count": 2,
            "double": 4,
            "remote": True,
            "last": "async",
        }
        assert events == ["remote-start", "remote-end", "computed", "async-computed"]

    async def test_synchronous_model_in_custom_hook_keeps_its_file_loading(
        self,
        tmp_path: Path,
    ) -> None:
        """Read files normally for a synchronous model created by a custom source hook."""
        dotenv = tmp_path / "nested.env"
        _ = dotenv.write_text("VALUE=nested")

        class Nested(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_file=dotenv
            )
            value: str

        class Settings(BaseSettings):
            value: str

            @classmethod
            def settings_customise_sources(
                cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
            ) -> tuple[SettingsSource, ...]:
                assert DEFER_SETTINGS_IO.get()
                nested = Nested()
                assert DEFER_SETTINGS_IO.get()
                return (nested.model_dump,)

        assert (await Settings.load()).value == "nested"
        assert not DEFER_SETTINGS_IO.get()


class TestAsyncSettingsConstruction:
    """Test custom constructors and models created during validation."""

    async def test_async_load_passes_inputs_to_required_constructor(
        self, tmp_path: Path
    ) -> None:
        """Pass loaded values to required constructor arguments before validation."""
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("FASTENV_ASYNC_COUNT=7")
        calls: list[str] = []

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_file=dotenv, env_prefix="FASTENV_ASYNC_"
            )
            count: int

            def __init__(self, count: Any) -> None:
                calls.append("construct")
                _ = dotenv.write_text("FASTENV_ASYNC_COUNT=invalid")
                super().__init__(count=count)

            @model_validator(mode="after")
            def record_validation(self) -> Self:
                calls.append("validate")
                return self

        assert (await Settings.load()).count == 7
        assert calls == ["construct", "validate"]

    async def test_async_load_preserves_constructor_input_transformations(
        self,
        tmp_path: Path,
    ) -> None:
        """Keep changes a custom constructor makes to loaded field values."""
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("FASTENV_ASYNC_COUNT=7")

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_file=dotenv, env_prefix="FASTENV_ASYNC_"
            )
            count: int

            def __init__(self, **values: Any) -> None:
                values["count"] = int(values["count"]) + 1
                _ = dotenv.write_text("FASTENV_ASYNC_COUNT=invalid")
                super().__init__(**values)

        assert (await Settings.load()).count == 8

    async def test_async_constructor_failure_does_not_bypass_next_sync_load(
        self,
        tmp_path: Path,
    ) -> None:
        """Read files normally after an asynchronous constructor fails."""
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("FASTENV_ASYNC_COUNT=7")

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_file=dotenv, env_prefix="FASTENV_ASYNC_"
            )
            count: int
            fail: bool = False

            def __init__(self, **values: Any) -> None:
                if values.get("fail"):
                    raise RuntimeError("constructor failed")
                super().__init__(**values)

        with pytest.raises(RuntimeError, match="constructor failed"):
            _ = await Settings.load(fail=True)
        assert Settings().count == 7

    async def test_async_construction_does_not_bypass_models_created_by_validation(
        self,
        tmp_path: Path,
    ) -> None:
        """Let models created by validators load their own settings."""
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("FASTENV_ASYNC_COUNT=7")
        nested_counts: list[int] = []

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_file=dotenv, env_prefix="FASTENV_ASYNC_"
            )
            count: int
            nested: bool = False

            @model_validator(mode="after")
            def build_nested(self) -> Self:
                if not self.nested:
                    nested_counts.append(type(self)(nested=True).count)
                return self

        assert (await Settings.load(count=3)).count == 3
        assert nested_counts == [7]

    async def test_async_prepared_inputs_belong_to_outer_instance(
        self, tmp_path: Path
    ) -> None:
        """Keep loaded values separate from another instance created by its constructor."""
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("FASTENV_ASYNC_COUNT=7")
        nested_counts: list[int] = []
        allocations: list[type[BaseSettings]] = []

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_file=dotenv, env_prefix="FASTENV_ASYNC_"
            )
            count: int
            nested: bool = False

            def __new__(cls, nested: bool = False, **values: Any) -> Self:
                allocations.append(cls)
                return super().__new__(cls, nested=nested, **values)

            def __init__(self, nested: bool = False, **values: Any) -> None:
                if not nested:
                    nested_counts.append(type(self)(nested=True).count)
                    _ = dotenv.write_text("FASTENV_ASYNC_COUNT=invalid")
                super().__init__(nested=nested, **values)

        assert (await Settings.load(count=3)).count == 3
        assert nested_counts == [7]
        assert allocations == [Settings, Settings]


class TestAsyncSettingsIsolation:
    """Test cleanup and separation of concurrent loads."""

    async def test_async_source_construction_failure_restores_context(
        self,
        tmp_path: Path,
    ) -> None:
        """Restore normal file loading after source construction fails."""

        class Broken(BaseSettings):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
            ) -> tuple[SettingsSource, ...]:
                assert DEFER_SETTINGS_IO.get()
                raise RuntimeError("source construction failed")

        with pytest.raises(RuntimeError, match="construction failed"):
            _ = await Broken.load()
        assert not DEFER_SETTINGS_IO.get()

        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("VALUE=loaded")
        source = DotEnvSettingsSource(BaseSettings, env_file=dotenv)
        assert source.env_vars == {"value": "loaded"}

    async def test_async_source_cancellation_restores_context(
        self, tmp_path: Path
    ) -> None:
        """Restore normal file loading when an asynchronous source is cancelled."""
        started = anyio.Event()
        cancelled = anyio.Event()

        async def suspended() -> dict[str, Any]:
            assert not DEFER_SETTINGS_IO.get()
            started.set()
            try:
                while True:
                    await anyio.lowlevel.checkpoint()
            finally:
                assert not DEFER_SETTINGS_IO.get()
                cancelled.set()

        class Settings(BaseSettings):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
            ) -> tuple[SettingsSource, ...]:
                return (suspended,)

        cancellation = anyio.CancelScope()

        async def load_until_cancelled() -> None:
            with cancellation:
                _ = await Settings.load()

        async with anyio.create_task_group() as tasks:
            _ = tasks.start_soon(load_until_cancelled)
            await started.wait()
            cancellation.cancel()
        assert cancelled.is_set()
        assert not DEFER_SETTINGS_IO.get()
        dotenv = tmp_path / "config.env"
        _ = dotenv.write_text("VALUE=loaded")
        assert DotEnvSettingsSource(BaseSettings, env_file=dotenv).env_vars == {
            "value": "loaded"
        }

    async def test_concurrent_async_loads_isolate_files_and_configuration(
        self,
        tmp_path: Path,
    ) -> None:
        """Keep concurrent loads separate without changing model options or the environment."""

        class Settings(BaseSettings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_prefix="FASTENV_ASYNC_"
            )
            value: str

        class Other(Settings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
                env_prefix="FASTENV_OTHER_"
            )

        files = [tmp_path / f"{index}.env" for index in range(8)]
        for index, file in enumerate(files):
            _ = file.write_text(
                f"FASTENV_{'ASYNC' if index % 2 else 'OTHER'}_VALUE={index}"
            )
        before = dict(os.environ)
        configs = dict(Settings.model_config), dict(Other.model_config)
        actual: dict[int, str] = {}

        async def load(index: int, file: Path) -> None:
            cls = Settings if index % 2 else Other
            actual[index] = (await cls.load(_env_file=file)).value
            assert not DEFER_SETTINGS_IO.get()

        async with anyio.create_task_group() as tasks:
            for index, file in enumerate(files):
                _ = tasks.start_soon(load, index, file)
        assert actual == {index: str(index) for index in range(8)}
        assert dict(os.environ) == before
        assert (Settings.model_config, Other.model_config) == configs
