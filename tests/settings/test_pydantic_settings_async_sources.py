# Source hooks intentionally accept arbitrary Pydantic field values.
# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
import anyio.lowlevel
import pytest
from pydantic import AliasChoices, BaseModel, Field
from pydantic.fields import FieldInfo

from fastenv.settings.pydantic_settings_sources import (
    _DEFER_SETTINGS_IO,
    DotEnvSettingsSource,
    InitSettingsSource,
    SecretsSettingsSource,
    SettingsError,
)


class SourceSettings(BaseModel):
    count: int = 0
    token: str = "default"
    items: list[int] = []


class TestAsyncDotenvSource:
    """Test asynchronous dotenv parsing and file reads."""

    @pytest.mark.anyio
    async def test_dotenv_load_defers_io_and_keeps_event_loop_responsive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Defer dotenv reads until loading and allow other tasks to run during I/O."""
        first = tmp_path / "first.env"
        second = tmp_path / "second.env"
        _ = first.write_text("COUNT=1 TOKEN='spaces and # hash' ITEMS='[2, 3]'\n")
        _ = second.write_text("export COUNT=4\n")
        environment = dict(os.environ)
        event_loop_thread = threading.get_ident()
        read_started = threading.Event()
        heartbeat = threading.Event()
        original_read_text = Path.read_text
        original_stat = Path.stat

        def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
            assert threading.get_ident() != event_loop_thread
            read_started.set()
            assert heartbeat.wait(timeout=3), "File reads must allow other tasks to run"
            return original_read_text(path, *args, **kwargs)

        def stat(path: Path, *args: Any, **kwargs: Any) -> os.stat_result:
            if path.is_relative_to(tmp_path):
                assert threading.get_ident() != event_loop_thread
            return original_stat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)
        monkeypatch.setattr(Path, "stat", stat)
        token = _DEFER_SETTINGS_IO.set(True)
        try:
            source = DotEnvSettingsSource(
                SourceSettings, env_file=[first, tmp_path / "missing", second]
            )
        finally:
            _DEFER_SETTINGS_IO.reset(token)
        assert not read_started.is_set()

        async def keep_running() -> None:
            with anyio.fail_after(3):
                while not read_started.is_set():
                    await anyio.lowlevel.checkpoint()
            heartbeat.set()

        result: dict[str, Any] = {}
        async with anyio.create_task_group() as tasks:
            _ = tasks.start_soon(keep_running)
            result = await source.load()
        assert result == {"count": "4", "token": "spaces and # hash", "items": [2, 3]}
        assert dict(os.environ) == environment

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        ("filtering", "extras"),
        [
            (None, {"app_unknown": "value", "other": "ignored"}),
            ("match_prefix", {"unknown": "value"}),
            ("only_existing", {}),
        ],
    )
    async def test_dotenv_async_filtering_and_decoding_hooks(
        self, tmp_path: Path, filtering: str | None, extras: dict[str, str]
    ) -> None:
        """Apply dotenv filtering, file encoding, and custom value decoding."""

        class CommaSeparatedSource(DotEnvSettingsSource):
            def decode_complex_value(
                self, field_name: str, field: FieldInfo, value: Any
            ) -> Any:
                assert field_name == "items"
                assert field.annotation == list[int]
                return [int(item) for item in str(value).split(",")]

        file = tmp_path / "settings.env"
        _ = file.write_text(
            "APP_COUNT=9 APP_TOKEN=caf\xe9 APP_ITEMS=1,2 APP_UNKNOWN=value OTHER=ignored",
            encoding="latin-1",
        )
        token = _DEFER_SETTINGS_IO.set(True)
        try:
            source = CommaSeparatedSource(
                SourceSettings,
                env_file=file,
                env_file_encoding="latin-1",
                env_prefix="APP_",
                dotenv_filtering=filtering,
            )
        finally:
            _DEFER_SETTINGS_IO.reset(token)
        assert await source.load() == {
            "count": "9",
            "token": "caf\xe9",
            "items": [1, 2],
            **extras,
        }

    @pytest.mark.anyio
    async def test_dotenv_async_case_none_and_empty_handling(
        self, tmp_path: Path
    ) -> None:
        """Honor case sensitivity, null values, and empty-value filtering."""
        file = tmp_path / "settings.env"
        _ = file.write_text("count=3 COUNT=4 token=nil items=\n")
        source = DotEnvSettingsSource(
            SourceSettings,
            env_file=file,
            case_sensitive=True,
            env_parse_none_str="nil",
            env_ignore_empty=True,
        )
        assert await source.load() == {"count": "3", "token": None, "COUNT": "4"}
        source.env_file = None
        assert await source.load() == {}

    @pytest.mark.anyio
    async def test_dotenv_async_parse_error_matches_synchronous_source(
        self,
        tmp_path: Path,
    ) -> None:
        """Report invalid JSON and allow another load after the file is corrected."""
        file = tmp_path / "settings.env"
        _ = file.write_text("ITEMS=invalid-json")
        source = DotEnvSettingsSource(SourceSettings, env_file=file)
        with pytest.raises(
            SettingsError, match='error parsing value for field "items"'
        ):
            _ = await source.load()
        _ = file.write_text("ITEMS='[1, 2]'")
        assert await source.load() == {"items": [1, 2]}


class TestAsyncSecretsSource:
    """Test asynchronous secret file reads and error handling."""

    @pytest.mark.anyio
    async def test_secrets_load_uses_async_io_and_preserves_alias_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read secrets off the event-loop thread and preserve alias priority."""

        class Settings(BaseModel):
            token: str = Field(validation_alias=AliasChoices("PRIMARY", "FALLBACK"))
            items: list[int]

        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        _ = (first / "primary").write_text("  preferred alias\n")
        _ = (second / "FALLBACK").write_text("lower-priority alias\n")
        _ = (first / "ITEMS").write_text("[0]")
        _ = (second / "items").write_text("  [1, 2]\n")
        environment = dict(os.environ)
        source = SecretsSettingsSource(Settings, secrets_dir=[first, second])
        event_loop_thread = threading.get_ident()
        operations: set[str] = set()

        def guard_io(method: Callable[..., Any]) -> Callable[..., Any]:
            def checked(
                path: str | os.PathLike[str] = ".", *args: Any, **kwargs: Any
            ) -> Any:
                if Path(path).is_relative_to(tmp_path):
                    assert threading.get_ident() != event_loop_thread
                    operations.add(method.__name__)
                return method(path, *args, **kwargs)

            return checked

        with monkeypatch.context() as patches:
            patches.setattr(Path, "read_text", guard_io(Path.read_text))
            patches.setattr(os, "stat", guard_io(os.stat))
            patches.setattr(os, "listdir", guard_io(os.listdir))
            patches.setattr(os, "scandir", guard_io(os.scandir))
            assert await source.load() == {
                "PRIMARY": "preferred alias",
                "items": [1, 2],
            }
        assert {"read_text", "stat"} <= operations
        assert {"listdir", "scandir"} & operations
        assert dict(os.environ) == environment
        _ = (second / "PRIMARY").write_text("updated")
        assert source()["PRIMARY"] == "updated"
        assert (await source.load())["PRIMARY"] == "updated"

    @pytest.mark.anyio
    async def test_secrets_async_directory_errors_and_missing_fields(
        self,
        tmp_path: Path,
    ) -> None:
        """Handle absent directories, invalid paths, and fields without secret files."""
        assert await SecretsSettingsSource(SourceSettings).load() == {}
        with pytest.warns(UserWarning, match="does not exist"):
            assert (
                await SecretsSettingsSource(SourceSettings, tmp_path / "missing").load()
                == {}
            )
        file = tmp_path / "file"
        _ = file.write_text("not a directory")
        with pytest.raises(SettingsError, match="must reference a directory"):
            _ = await SecretsSettingsSource(SourceSettings, file).load()
        (tmp_path / "count").mkdir()
        with pytest.warns(UserWarning, match="not a file"):
            assert await SecretsSettingsSource(SourceSettings, tmp_path).load() == {}

    @pytest.mark.anyio
    @pytest.mark.parametrize("directories", [None, []])
    async def test_secrets_async_preserves_subclass_output_without_directories(
        self,
        directories: list[Path] | None,
    ) -> None:
        """Keep custom source output when no secret directory is configured."""

        class DefaultingSource(SecretsSettingsSource):
            def __call__(self) -> dict[str, Any]:
                return {"token": "fallback", **super().__call__()}

        source = DefaultingSource(SourceSettings, secrets_dir=directories)
        assert await source.load() == source() == {"token": "fallback"}

    @pytest.mark.anyio
    async def test_secrets_async_read_errors_are_wrapped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Report secret read failures with their cause and allow a later retry."""
        _ = (tmp_path / "count").write_text("2")

        def denied(path: Path, *args: Any, **kwargs: Any) -> str:
            _ = path, args, kwargs
            raise PermissionError("denied")

        source = SecretsSettingsSource(SourceSettings, tmp_path)
        with monkeypatch.context() as patches:
            patches.setattr(Path, "read_text", denied)
            with pytest.raises(
                SettingsError, match='error getting value for field "count"'
            ) as error:
                _ = await source.load()
        assert isinstance(error.value.__cause__, PermissionError)
        assert await source.load() == {"count": "2"}

    @pytest.mark.anyio
    async def test_secrets_async_decode_hooks_and_failure_cleanup(
        self, tmp_path: Path
    ) -> None:
        """Use custom decoding and discard cached values after a decoding failure."""
        file = tmp_path / "ITEMS"
        _ = file.write_text("1,2")

        class CommaSeparatedSource(SecretsSettingsSource):
            def decode_complex_value(
                self, field_name: str, field: FieldInfo, value: Any
            ) -> Any:
                assert field_name == "items"
                assert field.annotation == list[int]
                return [int(item) for item in str(value).split(",")]

        source = CommaSeparatedSource(SourceSettings, tmp_path)
        assert await source.load() == {"items": [1, 2]}
        _ = file.write_text("invalid")
        with pytest.raises(
            SettingsError, match='error parsing value for field "items"'
        ):
            _ = await source.load()
        _ = file.write_text("3,4")
        assert source() == {"items": [3, 4]}


class TestAsyncSourceLoading:
    """Test shared source loading and cancellation behavior."""

    @pytest.mark.anyio
    async def test_non_file_source_async_protocol_preserves_inputs(self) -> None:
        """Return constructor inputs unchanged through asynchronous source loading."""
        source = InitSettingsSource(SourceSettings, {"count": 5})
        assert await source.load() == {"count": 5}

    @pytest.mark.anyio
    @pytest.mark.parametrize("source_kind", ["dotenv", "secrets"])
    async def test_file_sources_can_reload_after_cancellation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_kind: str
    ) -> None:
        """Allow dotenv and secret sources to reload after cancellation."""
        if source_kind == "dotenv":
            first = tmp_path / "first.env"
            blocked = tmp_path / "second.env"
            _ = first.write_text("COUNT=1 TOKEN=stale")
            _ = blocked.write_text("ITEMS='[2]'")
            source = DotEnvSettingsSource(SourceSettings, env_file=[first, blocked])
        else:
            first = tmp_path / "count"
            blocked = tmp_path / "items"
            _ = first.write_text("1")
            _ = blocked.write_text("[2]")
            source = SecretsSettingsSource(SourceSettings, secrets_dir=tmp_path)

        blocked_read = anyio.Event()
        cancellation = anyio.CancelScope()
        original_read_text = anyio.Path.read_text

        async def read_text(path: anyio.Path, *args: Any, **kwargs: Any) -> str:
            if Path(path) == blocked:
                blocked_read.set()
                await anyio.sleep_forever()
            return await original_read_text(path, *args, **kwargs)

        async def load_until_cancelled() -> None:
            with cancellation:
                _ = await source.load()

        with monkeypatch.context() as patches:
            patches.setattr(anyio.Path, "read_text", read_text)
            async with anyio.create_task_group() as tasks:
                _ = tasks.start_soon(load_until_cancelled)
                await blocked_read.wait()
                cancellation.cancel()

        assert cancellation.cancel_called
        _ = first.write_text("COUNT=7" if source_kind == "dotenv" else "7")
        _ = blocked.write_text("ITEMS='[3]'" if source_kind == "dotenv" else "[3]")
        assert await source.load() == {"count": "7", "items": [3]}
        assert source() == {"count": "7", "items": [3]}
