from __future__ import annotations

import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import pytest
from anyio import Path
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import fastenv


class LifespanState(TypedDict):
    settings: fastenv.DotEnv


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[LifespanState]:
    """Configure app lifespan.

    https://fastapi.tiangolo.com/advanced/events/
    https://www.starlette.io/lifespan/
    """
    env_file = os.environ["ENV_FILE"]
    settings = await fastenv.load_dotenv(env_file)
    lifespan_state: LifespanState = {"settings": settings}
    yield lifespan_state


app = FastAPI(lifespan=lifespan)


@app.get("/settings")
async def get_settings(request: Request) -> dict[str, str]:
    settings = request.state.settings
    return dict(settings)


@pytest.fixture
async def test_client(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[TestClient, None]:
    """Instantiate a FastAPI test client.

    https://fastapi.tiangolo.com/tutorial/testing/
    https://www.starlette.io/testclient/
    """
    monkeypatch.setenv("ENV_FILE", str(env_file))
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.anyio
async def test_fastapi_with_fastenv(test_client: TestClient) -> None:
    """Test loading a dotenv file into a FastAPI app with fastenv."""
    response = test_client.get("/settings")
    response_json = response.json()
    assert response_json["AWS_ACCESS_KEY_ID_EXAMPLE"] == "AKIAIOSFODNN7EXAMPLE"
