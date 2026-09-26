from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path
from typing import ClassVar, TypedDict, cast

import httpxyz
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fastenv import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    example_variable: str
    i_think_fastenv_is: str
    debug: bool = False


class LifespanState(TypedDict):
    settings: Settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[LifespanState]:
    """Configure app lifespan.

    https://fastapi.tiangolo.com/advanced/events/
    https://www.starlette.dev/lifespan/
    """
    settings = await Settings.load()
    lifespan_state: LifespanState = {"settings": settings}
    yield lifespan_state


app = FastAPI(lifespan=lifespan)


@app.get("/settings")
async def get_settings(request: Request) -> Settings:
    return request.state.settings  # pyright: ignore[reportAny]


@pytest.fixture
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create the dotenv file saved by the README quickstart."""
    monkeypatch.chdir(tmp_path)
    for name in ("EXAMPLE_VARIABLE", "I_THINK_FASTENV_IS", "DEBUG"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    _ = env_file.write_text(
        "EXAMPLE_VARIABLE=example_value\nI_THINK_FASTENV_IS=awesome\n"
    )
    return env_file


@pytest.mark.parametrize(
    ("overrides", "expected_example", "expected_debug"),
    [
        ({}, "example_value", False),
        (
            {"EXAMPLE_VARIABLE": "environment_value", "DEBUG": "true"},
            "environment_value",
            True,
        ),
    ],
)
@pytest.mark.usefixtures("settings_file")
def test_fastapi_with_fastenv(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, str],
    expected_example: str,
    expected_debug: bool,
) -> None:
    """Load typed settings at startup without changing the environment."""
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)
    before = dict(os.environ)
    with TestClient(app) as test_client:
        settings = cast(object, test_client.app_state["settings"])
        assert isinstance(settings, Settings)
        # Starlette's type annotations assume HTTPX2, but the client uses HTTPXYZ.
        response = cast(httpxyz.Client, test_client).get("/settings")
        assert response.status_code == 200
        assert response.json() == {
            "example_variable": expected_example,
            "i_think_fastenv_is": "awesome",
            "debug": expected_debug,
        }
        assert settings.debug is expected_debug
    assert dict(os.environ) == before


@pytest.mark.parametrize(
    ("contents", "error_field"),
    [
        (
            "EXAMPLE_VARIABLE=example_value\nI_THINK_FASTENV_IS=awesome\nDEBUG=invalid",
            "debug",
        ),
        ("EXAMPLE_VARIABLE=example_value\n", "i_think_fastenv_is"),
    ],
)
def test_fastapi_rejects_invalid_settings_at_startup(
    settings_file: Path, contents: str, error_field: str
) -> None:
    _ = settings_file.write_text(contents)
    before = dict(os.environ)
    with pytest.raises(ValidationError) as exc_info, ExitStack() as stack:
        stack.enter_context(TestClient(app))
    assert exc_info.value.errors()[0]["loc"] == (error_field,)
    assert dict(os.environ) == before
