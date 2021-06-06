from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from starlette.datastructures import Secret

from fastenv import starlette_config

# TODO: Starlette `Config` pytest fixture


def test_default_settings(settings: starlette_config.Config) -> None:
    """Test default application settings."""
    assert settings.NAME == "fastenv"
    assert isinstance(settings.AWS_SECRET_ACCESS_KEY, Secret)
    assert (
        str(settings.EXTERNAL_SERVICE_PASSWORD)
        == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    )


def test_read_env_string(env_string: str) -> None:
    """Test the `read_env_string` method on the Starlette `Config` subclass."""
    config = starlette_config.Config(env_string=env_string)
    EMPTY_VARIABLE = config("EMPTY_VARIABLE", cast=str)
    PASSWORD_VARIABLE = config("PASSWORD_VARIABLE", cast=Secret)
    USUAL_VARIABLE = config("USUAL_VARIABLE", cast=str)
    VARIABLE_WITH_QUOTES = config("VARIABLE_WITH_QUOTES", cast=str)
    VARIABLE_WITH_WHITESPACE = config("VARIABLE_WITH_WHITESPACE", cast=str)
    assert EMPTY_VARIABLE == ""
    assert str(PASSWORD_VARIABLE) == "64w2Q$!&EXAMPLE"
    assert USUAL_VARIABLE == "value"
    assert VARIABLE_WITH_QUOTES == "just_the_text"
    assert VARIABLE_WITH_WHITESPACE == "no_whitespace"
    assert "comment" not in config.file_values


def test_read_pyproject_toml() -> None:
    """Test the `read_pyproject_toml` method on the Starlette `Config` subclass."""
    config = starlette_config.Config(
        toml=Path(__file__).parents[1].joinpath("pyproject.toml")
    )
    config.read_pyproject_toml()
    DESCRIPTION = config("DESCRIPTION", cast=str)
    NAME = config("NAME", cast=str)
    REPOSITORY = config("REPOSITORY", cast=str)
    VERSION = config("VERSION", cast=str)
    assert "github" in REPOSITORY
