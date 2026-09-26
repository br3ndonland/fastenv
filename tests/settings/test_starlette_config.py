from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import assert_type, cast

import anyio
import pytest
from starlette.config import Config as StarletteConfig
from starlette.config import Environ, EnvironError
from starlette.datastructures import CommaSeparatedStrings, Secret

import fastenv
from fastenv.settings.starlette_config import Config
from fastenv.utilities import read_toml_file


def test_starlette_config_public_export() -> None:
    assert fastenv.StarletteConfig is Config
    assert issubclass(Config, StarletteConfig)


def test_starlette_config_without_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (tmp_path / ".env").write_text("FASTENV_CONFIG_TEST_VALUE=dotenv\n")
    _ = (tmp_path / "pyproject.toml").write_text(
        '[project]\nfastenv_config_test_value = "toml"\n'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FASTENV_CONFIG_TEST_VALUE", "environment")
    config = Config()
    assert config("FASTENV_CONFIG_TEST_VALUE") == "environment"
    isolated_config = Config(environ={})
    assert isolated_config("FASTENV_CONFIG_TEST_VALUE", default="default") == "default"


@pytest.mark.parametrize("path_type", ("str", "pathlib", "anyio"))
def test_starlette_config_dotenv_path(tmp_path: Path, path_type: str) -> None:
    env_file = tmp_path / ".env"
    _ = env_file.write_text("FASTENV_CONFIG_TEST_VALUE=dotenv\n")
    path: str | os.PathLike[str] = str(env_file)
    if path_type == "pathlib":
        path = env_file
    elif path_type == "anyio":
        path = anyio.Path(env_file)
    config = Config(path, environ={})
    assert config("FASTENV_CONFIG_TEST_VALUE") == "dotenv"


def test_starlette_config_dotenv_parser_and_isolation(tmp_path: Path) -> None:
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
    config = Config(env_file, environ=environ)
    assert config("LOWER_KEY") == "last value"
    assert config("QUOTED_HASH") == "value#not-comment"
    assert config("EQUALS") == "left=right"
    assert config("EMPTY") == ""
    assert config("MULTILINE") == "first\nsecond"
    assert config("EXISTING") == "environment"
    assert config("BARE_KEY", default="unset") == "unset"
    assert Config(environ={})("LOWER_KEY", default="unset") == "unset"
    assert environ == {"EXISTING": "environment"}
    assert dict(os.environ) == process_environ


@pytest.mark.parametrize("use_tuple", (False, True))
def test_starlette_config_source_precedence(tmp_path: Path, use_tuple: bool) -> None:
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
    config = Config(files, environ=environ, toml_file=toml_file)
    assert config("SHARED", default="default") == "environment"
    assert config("FILE_VALUE", default="default") == "second"
    assert config("EARLIER", default="default") == "first"
    assert config("ONLY_TOML", default="default") == "toml"
    assert config("ONLY_DEFAULT", default="default") == "default"
    assert environ == {"SHARED": "environment"}


def test_starlette_config_empty_file_sequence() -> None:
    config = Config([], environ={})
    assert config("MISSING", default="default") == "default"


def test_starlette_config_toml_native_values(tmp_path: Path) -> None:
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
    config = Config(environ={}, toml_file=anyio.Path(toml_file), toml_table="settings")
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


def test_starlette_config_positional_arguments_and_encoding(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _ = env_file.write_text("APP_MESSAGE=ol\xe1\n", encoding="latin-1")
    config = Config(env_file, {}, "APP_", "latin-1")
    assert config("MESSAGE") == "ol\xe1"


def test_starlette_config_prefix_applies_to_every_source(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _ = env_file.write_text("APP_FILE=file\nAPP_ENV=file\n")
    toml_file = tmp_path / "settings.toml"
    _ = toml_file.write_text('[project]\napp_toml = "toml"\n')
    config = Config(
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


def test_starlette_config_casting_and_defaults() -> None:
    config = Config(
        environ={"COUNT": "42", "DEBUG": "true", "SECRET": "secret", "HOSTS": "a, b"}
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


def test_starlette_config_environ_read_protection(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _ = env_file.write_text("FROM_FILE=file\n")
    environ = Environ({"FROM_ENV": "environment"})
    config = Config(env_file, environ=environ)
    assert config("FROM_ENV") == "environment"
    assert config("FROM_FILE") == "file"
    with pytest.raises(EnvironError):
        environ["FROM_ENV"] = "changed"
    with pytest.raises(EnvironError):
        del environ["FROM_ENV"]
    with pytest.raises(EnvironError):
        environ["FROM_FILE"] = "changed"
    environ["UNREAD"] = "allowed"
    assert environ["UNREAD"] == "allowed"


@pytest.mark.parametrize("suppress", (False, True))
@pytest.mark.parametrize("failure", ("missing", "directory", "parse", "decode"))
def test_starlette_config_dotenv_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    suppress: bool,
    failure: str,
) -> None:
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
        config = Config(env_file, environ={}, raise_exceptions=False)
        assert config("PARTIAL", default="absent") == "absent"
    else:
        with pytest.raises(expected_exception):
            _ = Config(env_file, environ={})
    assert str(env_file) in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)


def test_starlette_config_skips_only_failed_dotenv_source(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    first_file = tmp_path / ".env.first"
    _ = first_file.write_text("FIRST=first SHARED=first\n")
    broken_file = tmp_path / ".env.broken"
    _ = broken_file.write_text(
        "PARTIAL=discarded SHARED=broken\nBROKEN='unterminated\n"
    )
    last_file = tmp_path / ".env.last"
    _ = last_file.write_text("LAST=last\n")
    config = Config(
        [first_file, broken_file, last_file], environ={}, raise_exceptions=False
    )
    assert config("FIRST") == "first"
    assert config("SHARED") == "first"
    assert config("LAST") == "last"
    assert config("PARTIAL", default="absent") == "absent"
    assert str(broken_file) in caplog.text


@pytest.mark.parametrize("suppress", (False, True))
@pytest.mark.parametrize("failure", ("missing", "parse", "missing_table", "not_table"))
def test_starlette_config_toml_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    suppress: bool,
    failure: str,
) -> None:
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
        config = Config(
            env_file, environ={}, toml_file=toml_file, raise_exceptions=False
        )
        assert config("FROM_FILE") == "file"
    else:
        with pytest.raises(expected_exception):
            _ = Config(env_file, environ={}, toml_file=toml_file)
    assert str(toml_file) in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)


@pytest.mark.anyio
async def test_starlette_config_constructed_in_running_event_loop(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    _ = env_file.write_text("FROM_FILE=file\n")
    toml_file = tmp_path / "settings.toml"
    _ = toml_file.write_text('[project]\nname = "example"\n')
    config = Config(env_file, environ={}, toml_file=toml_file)
    assert config("FROM_FILE") == "file"
    assert config("NAME") == "example"


def test_fastenv_import_without_starlette() -> None:
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


def test_starlette_config_repository_project_metadata() -> None:
    toml_file = Path(__file__).resolve().parents[2] / "pyproject.toml"
    config = Config(environ={}, toml_file=toml_file)
    assert config("NAME") == "fastenv"
    assert config("DESCRIPTION") == (
        "Unified environment variable and settings management for FastAPI and beyond."
    )
    assert config("URLS") == {
        "Documentation": "https://fastenv.bws.bio",
        "Homepage": "https://github.com/br3ndonland/fastenv",
        "Repository": "https://github.com/br3ndonland/fastenv",
    }


def test_starlette_config_falsey_toml_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    assert read_toml_file() == expected
    config = Config(environ={}, toml_file=toml_file)
    for key, value in expected.items():
        result = config(key, default="fallback")
        assert result == value
        assert type(result) is type(value)


def test_starlette_config_reads_live_environ_mapping(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    _ = env_file.write_text("VALUE=file\n")
    environ = {"VALUE": "initial"}
    config = Config(env_file, environ=environ)
    assert config("VALUE") == "initial"
    environ["VALUE"] = "updated"
    assert config("VALUE") == "updated"
    environ["VALUE"] = ""
    assert config("VALUE", default="fallback") == ""
    del environ["VALUE"]
    assert config("VALUE") == "file"


def test_starlette_config_strict_failure_preserves_environ(tmp_path: Path) -> None:
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
        _ = Config([first_file, broken_file], environ=environ)
    assert environ == supplied_environ
    assert dict(os.environ) == process_environ
