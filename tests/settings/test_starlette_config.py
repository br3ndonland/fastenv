from __future__ import annotations

import datetime
import os
import subprocess
import sys
import threading
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, assert_type, cast

import anyio
import pytest
import starlette.config
from starlette.datastructures import CommaSeparatedStrings, Secret

from fastenv.settings.starlette_config import StarletteConfig
from fastenv.utilities import read_toml_file

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestStarletteConfigConstruction:
    """Test public imports and config construction."""

    def test_starlette_config_public_export(self) -> None:
        """Assert that the public export subclasses Starlette's `Config`."""
        assert issubclass(StarletteConfig, starlette.config.Config)

    def test_fastenv_import_without_starlette(self) -> None:
        """Assert that fastenv remains usable without Starlette installed."""
        script = """
import sys

from importlib.abc import MetaPathFinder


class BlockStarlette(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "starlette":
            raise ModuleNotFoundError("No module named 'starlette'", name="starlette")
        return None


sys.meta_path.insert(0, BlockStarlette())
import fastenv

assert callable(fastenv.load_dotenv)
assert callable(fastenv.DotEnv)
assert not hasattr(fastenv, "StarletteConfig")
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    def test_starlette_config_without_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read environment values without discovering files implicitly."""
        _ = (tmp_path / ".env").write_text("FASTENV_CONFIG_TEST_VALUE=dotenv\n")
        _ = (tmp_path / "pyproject.toml").write_text(
            '[project]\nfastenv_config_test_value = "toml"\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FASTENV_CONFIG_TEST_VALUE", "environment")
        config = StarletteConfig()
        assert config("FASTENV_CONFIG_TEST_VALUE") == "environment"
        isolated_config = StarletteConfig(environ={})
        assert (
            isolated_config("FASTENV_CONFIG_TEST_VALUE", default="default") == "default"
        )

    def test_starlette_config_constructor_loads_multiple_sources(
        self, tmp_path: Path
    ) -> None:
        """Load ordered dotenv files and TOML before the constructor returns."""
        first = tmp_path / ".env"
        second = tmp_path / ".env.local"
        toml_file = tmp_path / "settings.toml"
        _ = first.write_text("APP_PORT=8000 APP_NAME=base APP_DEBUG=false\n")
        _ = second.write_text("APP_PORT=9000 APP_NAME=local\n")
        _ = toml_file.write_text("[settings]\napp_port = 7000\napp_count = 3\n")
        environ = {"APP_NAME": "environment"}
        process_environ = dict(os.environ)
        config = StarletteConfig(
            [str(first), anyio.Path(second)],
            environ,
            "APP_",
            toml_file=toml_file,
            toml_table="settings",
        )
        assert config("NAME") == "environment"
        assert config("PORT", cast=int) == 9000
        assert config("DEBUG", cast=bool) is False
        assert config("COUNT") == 3
        assert environ == {"APP_NAME": "environment"}
        assert dict(os.environ) == process_environ

    def test_starlette_config_constructor_encoding(self, tmp_path: Path) -> None:
        """Accept one dotenv path and Starlette's positional encoding argument."""
        env_file = tmp_path / ".env"
        _ = env_file.write_bytes(b"APP_MESSAGE=ol\xe1\n")
        config = StarletteConfig(env_file, {}, "APP_", "latin-1")
        assert config("MESSAGE") == "ol\xe1"

    @pytest.mark.parametrize("suppress", (False, True))
    def test_starlette_config_constructor_file_errors(
        self, tmp_path: Path, suppress: bool
    ) -> None:
        """Apply strict and suppressed file errors during synchronous construction."""
        missing = tmp_path / "missing"
        if suppress:
            assert (
                StarletteConfig(
                    missing, environ={}, toml_file=missing, raise_exceptions=False
                )("MISSING", default="default")
                == "default"
            )
        else:
            with pytest.raises(FileNotFoundError):
                _ = StarletteConfig(missing, environ={}, toml_file=missing)

    @pytest.mark.anyio
    async def test_starlette_config_constructor_in_running_event_loop(
        self, tmp_path: Path
    ) -> None:
        """Allow environment-only construction but reject nested event loops."""
        config = StarletteConfig(environ={"VALUE": "environment"})
        assert config("VALUE") == "environment"
        with pytest.raises(RuntimeError, match="Already running"):
            _ = StarletteConfig(tmp_path / ".env", raise_exceptions=False)

    @pytest.mark.anyio
    async def test_starlette_config_load_preserves_subclass(
        self, tmp_path: Path
    ) -> None:
        """Assert that the loader returns an instance of the calling subclass."""

        class AppConfig(StarletteConfig):
            pass

        env_file = tmp_path / ".env"
        _ = env_file.write_text("VALUE=file\n")
        config = await AppConfig.load(env_file, environ={})
        assert type(assert_type(config, AppConfig)) is AppConfig
        assert config("VALUE") == "file"


class TestStarletteConfigDotenv:
    """Test dotenv paths, parsing, and encoding."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("path_type", ("str", "pathlib", "anyio"))
    async def test_starlette_config_dotenv_path(
        self, tmp_path: Path, path_type: str
    ) -> None:
        """Load dotenv values from string, pathlib, and AnyIO paths."""
        env_file = tmp_path / ".env"
        _ = env_file.write_text("FASTENV_CONFIG_TEST_VALUE=dotenv\n")
        path: str | os.PathLike[str] = str(env_file)
        if path_type == "pathlib":
            path = env_file
        elif path_type == "anyio":
            path = anyio.Path(env_file)
        config = await StarletteConfig.load(path, environ={})
        assert config("FASTENV_CONFIG_TEST_VALUE") == "dotenv"

    @pytest.mark.anyio
    async def test_starlette_config_dotenv_parser_and_isolation(
        self, tmp_path: Path
    ) -> None:
        """Parse dotenv syntax without changing the environment or other configs."""
        env_file = tmp_path / ".env"
        _ = env_file.write_text(
            """# Full-line comment
export lower_key='first value' # Inline comment
lower_key='last value'
quoted_hash="value#not-comment" equals=left=right
empty=
bare_key
multiline='first
second'
existing=file
"""
        )
        environ = {"EXISTING": "environment"}
        process_environ = dict(os.environ)
        config = await StarletteConfig.load(env_file, environ=environ)
        assert config("LOWER_KEY") == "last value"
        assert config("QUOTED_HASH") == "value#not-comment"
        assert config("EQUALS") == "left=right"
        assert config("EMPTY") == ""
        assert config("MULTILINE") == "first\nsecond"
        assert config("EXISTING") == "environment"
        assert config("BARE_KEY", default="unset") == "unset"
        assert StarletteConfig(environ={})("LOWER_KEY", default="unset") == "unset"
        assert environ == {"EXISTING": "environment"}
        assert dict(os.environ) == process_environ

    @pytest.mark.anyio
    async def test_starlette_config_empty_file_sequence(self) -> None:
        """Accept an empty file sequence and use setting defaults."""
        config = await StarletteConfig.load([], environ={})
        assert config("MISSING", default="default") == "default"

    @pytest.mark.anyio
    async def test_starlette_config_positional_arguments_and_encoding(
        self,
        tmp_path: Path,
    ) -> None:
        """Load an encoded dotenv file with positional loader arguments."""
        env_file = tmp_path / ".env"
        _ = env_file.write_text("APP_MESSAGE=ol\xe1\n", encoding="latin-1")
        config = await StarletteConfig.load(env_file, {}, "APP_", "latin-1")
        assert config("MESSAGE") == "ol\xe1"


class TestStarletteConfigTOML:
    """Test TOML metadata, native values, and parsing."""

    @pytest.mark.anyio
    async def test_starlette_config_toml_native_values(self, tmp_path: Path) -> None:
        """Load a selected TOML table while preserving native types and nested keys."""
        toml_file = tmp_path / "settings.toml"
        _ = toml_file.write_text(
            """[settings]
name = "example"
count = 3
ratio = 0.25
enabled = true
items = ["one", "two"]
date = 2026-09-25
[settings.nested]
MixedCase = "retained"
"""
        )
        process_environ = dict(os.environ)
        config = await StarletteConfig.load(
            environ={}, toml_file=anyio.Path(toml_file), toml_table="settings"
        )
        assert assert_type(config.file_values, dict[str, object])["COUNT"] == 3
        assert config("NAME") == "example"
        assert assert_type(config("COUNT"), object) == 3
        assert config("RATIO") == 0.25
        assert config("ENABLED") is True
        assert config("ENABLED", cast=bool) is True
        assert config("ITEMS") == ["one", "two"]
        assert config("DATE") == datetime.date(2026, 9, 25)
        assert config("NESTED") == {"MixedCase": "retained"}
        assert dict(os.environ) == process_environ

    @pytest.mark.anyio
    async def test_starlette_config_repository_project_metadata(self) -> None:
        """Read project metadata from the repository's `pyproject.toml`."""
        toml_file = Path(__file__).resolve().parents[2] / "pyproject.toml"
        config = await StarletteConfig.load(environ={}, toml_file=toml_file)
        assert config("NAME") == "fastenv"
        assert config("URLS") == {
            "Documentation": "https://fastenv.bws.bio",
            "Homepage": "https://github.com/br3ndonland/fastenv",
            "Repository": "https://github.com/br3ndonland/fastenv",
        }

    @pytest.mark.anyio
    async def test_starlette_config_falsy_toml_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preserve falsy TOML values instead of replacing them with defaults."""
        toml_file = tmp_path / "pyproject.toml"
        _ = toml_file.write_text(
            """[project]
zero = 0
false = false
empty_list = []
empty_dict = {}
empty_string = ""
"""
        )
        monkeypatch.chdir(tmp_path)
        expected: dict[str, object] = {
            "ZERO": 0,
            "FALSE": False,
            "EMPTY_LIST": [],
            "EMPTY_DICT": {},
            "EMPTY_STRING": "",
        }
        assert await read_toml_file() == expected
        config = await StarletteConfig.load(environ={}, toml_file=toml_file)
        for key, value in expected.items():
            result = config(key, default="fallback")
            assert result == value
            assert type(result) is type(value)

    @pytest.mark.anyio
    async def test_starlette_config_toml_rejects_bare_carriage_returns(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject bare carriage returns without normalizing invalid TOML."""
        toml_file = tmp_path / "settings.toml"
        _ = toml_file.write_bytes(b'[project]\rname = "invalid"\r')
        with pytest.raises(tomllib.TOMLDecodeError):
            _ = await read_toml_file(toml_file)
        with pytest.raises(tomllib.TOMLDecodeError):
            _ = await StarletteConfig.load(environ={}, toml_file=toml_file)


class TestStarletteConfigLookups:
    """Test source precedence and inherited Starlette lookup behavior."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("use_tuple", (False, True))
    async def test_starlette_config_source_precedence(
        self, tmp_path: Path, use_tuple: bool
    ) -> None:
        """Prefer environment values, later dotenv files, TOML, then defaults."""
        toml_file = tmp_path / "settings.toml"
        _ = toml_file.write_text(
            """[project]
shared = "toml"
file_value = "toml"
earlier = "toml"
only_toml = "toml"
"""
        )
        first_file = tmp_path / ".env"
        _ = first_file.write_text("SHARED=first FILE_VALUE=first EARLIER=first\n")
        second_file = tmp_path / ".env.local"
        _ = second_file.write_text("SHARED=second FILE_VALUE=second\n")
        files = (first_file, second_file) if use_tuple else [first_file, second_file]
        environ = {"SHARED": "environment"}
        config = await StarletteConfig.load(files, environ=environ, toml_file=toml_file)
        assert config("SHARED", default="default") == "environment"
        assert config("FILE_VALUE", default="default") == "second"
        assert config("EARLIER", default="default") == "first"
        assert config("ONLY_TOML", default="default") == "toml"
        assert config("ONLY_DEFAULT", default="default") == "default"
        assert environ == {"SHARED": "environment"}

    @pytest.mark.anyio
    async def test_starlette_config_prefix_applies_to_every_source(
        self, tmp_path: Path
    ) -> None:
        """Apply the environment prefix to lookups across all sources."""
        env_file = tmp_path / ".env"
        _ = env_file.write_text("APP_FILE=file\nAPP_ENV=file\n")
        toml_file = tmp_path / "settings.toml"
        _ = toml_file.write_text('[project]\napp_toml = "toml"\n')
        config = await StarletteConfig.load(
            env_file,
            environ={"APP_ENV": "environment"},
            env_prefix="APP_",
            toml_file=toml_file,
        )
        assert config("ENV") == "environment"
        assert config("FILE") == "file"
        assert config("TOML") == "toml"
        with pytest.raises(KeyError, match="APP_MISSING"):
            _ = config("MISSING")

    def test_starlette_config_casting_and_defaults(self) -> None:
        """Apply casts and defaults, and reject missing or invalid settings."""
        config = StarletteConfig(
            environ={
                "COUNT": "42",
                "DEBUG": "true",
                "SECRET": "secret",
                "HOSTS": "a, b",
            }
        )
        assert assert_type(config("COUNT", cast=int), int) == 42
        assert assert_type(config("DEBUG", cast=bool), bool) is True
        assert str(config("SECRET", cast=Secret)) == "secret"
        assert list(config("HOSTS", cast=CommaSeparatedStrings)) == [
            "a",
            "b",
        ]
        assert config("MISSING", cast=int, default="7") == 7
        assert config("MISSING", default=None) is None
        assert cast(str, config.get("COUNT")) == "42"
        with pytest.raises(KeyError, match="MISSING"):
            _ = config("MISSING")
        with pytest.raises(ValueError, match="DEBUG"):
            _ = config("DEBUG", cast=int)
        with pytest.raises(ValueError, match="COUNT"):
            _ = config("COUNT", cast=bool)

    @pytest.mark.anyio
    async def test_starlette_config_environ_read_behavior(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Assert that `fastenv.StarletteConfig` retains the same environment variable
        read behavior as Starlette `Config`.

        As described in the comparisons docs, Starlette has an opinionated one-way
        configuration preference (environment variables -> Starlette `Config` instance).
        To avoid modifying environment variables after they have been loaded into a
        Starlette `Config` instance, Starlette provides its own mapping onto
        `os.environ` (`starlette.config.environ`), which will raise an exception on
        attempts to change an environment variable that has already been loaded into a
        corresponding setting on a `Config` instance.

        This protection only applies to `starlette.config.environ`. Updates to
        `os.environ` bypass the protection, and future calls to the `Config` instance
        may then read updated values from `os.environ` depending on config precedence.

        While it is useful to have `starlette.config.environ` synchronized with
        `os.environ`, the downside is that `starlette.config.environ` contains local
        environment variables loaded from `os.environ`, and therefore wouldn't typically
        be dumped to a file.

        This is mostly a test of Starlette's behavior rather than fastenv's behavior,
        and therefore could be considered unnecessary. However, as this behavior is
        described in the fastenv docs, it is helpful to have a test in this project
        to ensure the docs continue to accurately represent Starlette's behavior.
        """
        mocker.patch.dict(os.environ, clear=True)
        env_file = tmp_path / ".env"
        _ = env_file.write_text("FOO_VARIABLE=file\nFROM_FILE=file\n")
        environ = starlette.config.Environ(os.environ)
        environ["FOO_VARIABLE"] = "bar"
        config = await StarletteConfig.load(env_file, environ=environ)
        assert config("FOO_VARIABLE", cast=str, default="baz") == "bar"
        assert config("FROM_FILE") == "file"
        with pytest.raises(starlette.config.EnvironError):
            environ["FOO_VARIABLE"] = "foo"
        with pytest.raises(starlette.config.EnvironError):
            del environ["FOO_VARIABLE"]
        with pytest.raises(starlette.config.EnvironError):
            environ["FROM_FILE"] = "changed"
        os.environ["FOO_VARIABLE"] = "foo"
        assert environ["FOO_VARIABLE"] == "foo"
        assert config("FOO_VARIABLE", cast=str, default="baz") == "foo"
        os.environ["FOO_VARIABLE"] = ""
        assert config("FOO_VARIABLE", default="baz") == ""
        del os.environ["FOO_VARIABLE"]
        assert config("FOO_VARIABLE") == "file"


class TestStarletteConfigFileErrors:
    """Test strict and suppressed file loading errors."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("suppress", (False, True))
    @pytest.mark.parametrize("failure", ("missing", "directory", "parse", "decode"))
    async def test_starlette_config_dotenv_failure(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        suppress: bool,
        failure: str,
    ) -> None:
        """Log dotenv errors and either raise them or skip the failed source."""
        env_file = tmp_path / ".env"
        expected_exception: type[Exception] = FileNotFoundError
        if failure == "directory":
            env_file.mkdir()
            expected_exception = IsADirectoryError
        elif failure == "parse":
            _ = env_file.write_text("PARTIAL=discarded\nBROKEN='unterminated\n")
            expected_exception = ValueError
        elif failure == "decode":
            _ = env_file.write_bytes(b"BROKEN=\xff\n")
            expected_exception = UnicodeDecodeError
        if suppress:
            config = await StarletteConfig.load(
                env_file, environ={}, raise_exceptions=False
            )
            assert config("PARTIAL", default="absent") == "absent"
        else:
            with pytest.raises(expected_exception):
                _ = await StarletteConfig.load(env_file, environ={})
        assert str(env_file) in caplog.text
        assert any(record.levelname == "ERROR" for record in caplog.records)

    @pytest.mark.anyio
    async def test_starlette_config_skips_only_failed_dotenv_source(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Keep valid sources and discard every value from a failed dotenv file."""
        first_file = tmp_path / ".env.first"
        _ = first_file.write_text("FIRST=first SHARED=first\n")
        broken_file = tmp_path / ".env.broken"
        _ = broken_file.write_text(
            "PARTIAL=discarded SHARED=broken\nBROKEN='unterminated\n"
        )
        last_file = tmp_path / ".env.last"
        _ = last_file.write_text("LAST=last\n")
        config = await StarletteConfig.load(
            [first_file, broken_file, last_file], environ={}, raise_exceptions=False
        )
        assert config("FIRST") == "first"
        assert config("SHARED") == "first"
        assert config("LAST") == "last"
        assert config("PARTIAL", default="absent") == "absent"
        assert str(broken_file) in caplog.text

    @pytest.mark.anyio
    @pytest.mark.parametrize("suppress", (False, True))
    @pytest.mark.parametrize(
        "failure", ("missing", "parse", "missing_table", "not_table")
    )
    async def test_starlette_config_toml_failure(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        suppress: bool,
        failure: str,
    ) -> None:
        """Log TOML errors and either raise them or continue with dotenv sources."""
        toml_file = tmp_path / "settings.toml"
        expected_exception: type[Exception] = FileNotFoundError
        if failure == "parse":
            _ = toml_file.write_text("[project\n")
            expected_exception = tomllib.TOMLDecodeError
        elif failure == "missing_table":
            _ = toml_file.write_text('[other]\nname = "example"\n')
            expected_exception = KeyError
        elif failure == "not_table":
            _ = toml_file.write_text('project = "not a table"\n')
            expected_exception = TypeError
        env_file = tmp_path / ".env"
        _ = env_file.write_text("FROM_FILE=file\n")
        if suppress:
            config = await StarletteConfig.load(
                env_file, environ={}, toml_file=toml_file, raise_exceptions=False
            )
            assert config("FROM_FILE") == "file"
        else:
            with pytest.raises(expected_exception):
                _ = await StarletteConfig.load(
                    env_file, environ={}, toml_file=toml_file
                )
        assert str(toml_file) in caplog.text
        assert any(record.levelname == "ERROR" for record in caplog.records)

    @pytest.mark.anyio
    async def test_starlette_config_strict_failure_preserves_environ(
        self,
        tmp_path: Path,
    ) -> None:
        """Leave both environment mappings unchanged when file loading fails."""
        first_file = tmp_path / ".env.first"
        _ = first_file.write_text("FASTENV_CONFIG_TEST_VALUE=first\n")
        broken_file = tmp_path / ".env.broken"
        _ = broken_file.write_text(
            "FASTENV_CONFIG_TEST_VALUE=partial BROKEN='unterminated\n"
        )
        environ = {"FASTENV_CONFIG_TEST_VALUE": "environment"}
        supplied_environ = dict(environ)
        process_environ = dict(os.environ)
        with pytest.raises(ValueError, match="No closing quotation"):
            _ = await StarletteConfig.load([first_file, broken_file], environ=environ)
        assert environ == supplied_environ
        assert dict(os.environ) == process_environ


class TestStarletteConfigAsyncLoading:
    """Test event loop responsiveness and cancellation during file loading."""

    @pytest.mark.anyio
    async def test_starlette_config_loaded_in_running_event_loop(
        self,
        tmp_path: Path,
    ) -> None:
        """Load dotenv and TOML files inside an existing event loop."""
        env_file = tmp_path / ".env"
        _ = env_file.write_text("FROM_FILE=file\n")
        toml_file = tmp_path / "settings.toml"
        _ = toml_file.write_text('[project]\nname = "example"\n')
        config = await StarletteConfig.load(env_file, environ={}, toml_file=toml_file)
        assert config("FROM_FILE") == "file"
        assert config("NAME") == "example"

    @pytest.mark.anyio
    async def test_starlette_config_loading_keeps_event_loop_responsive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Allow another async task to run while a file read is blocked."""
        env_file = tmp_path / ".env"
        _ = env_file.write_text("VALUE=file\n")
        read_started = threading.Event()
        allow_read = threading.Event()
        read_text = Path.read_text

        def delayed_read(
            path: Path,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ) -> str:
            assert newline is None
            read_started.set()
            assert allow_read.wait(timeout=5), "The file read blocked the event loop"
            return read_text(path, encoding=encoding, errors=errors)

        async def release_from_event_loop() -> None:
            assert await anyio.to_thread.run_sync(read_started.wait, 5)
            allow_read.set()

        monkeypatch.setattr(Path, "read_text", delayed_read)
        async with anyio.create_task_group() as task_group:
            _ = task_group.start_soon(release_from_event_loop)
            config = await StarletteConfig.load(env_file, environ={})
            assert config("VALUE") == "file"
            assert read_started.is_set()

    @pytest.mark.anyio
    @pytest.mark.parametrize("source", ("dotenv", "toml"))
    async def test_starlette_config_cancellation_is_not_suppressed(
        self, tmp_path: Path, source: str
    ) -> None:
        """Propagate cancellation even when file errors are suppressed."""
        env_file = tmp_path / ".env"
        _ = env_file.write_text("VALUE=file\n")
        toml_file = tmp_path / "settings.toml"
        _ = toml_file.write_text('[project]\nvalue = "toml"\n')
        with anyio.CancelScope() as scope:
            scope.cancel()
            with pytest.raises(anyio.get_cancelled_exc_class()):
                _ = await StarletteConfig.load(
                    env_file if source == "dotenv" else None,
                    environ={},
                    toml_file=toml_file if source == "toml" else None,
                    raise_exceptions=False,
                )
