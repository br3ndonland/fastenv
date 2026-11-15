# pyright: reportAny=false
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypedDict

import fastenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class LifespanState(TypedDict):
    config: fastenv.StarletteConfig


@asynccontextmanager
async def lifespan(_: Starlette) -> AsyncGenerator[LifespanState]:
    config = await fastenv.StarletteConfig.load(".env")
    yield {"config": config}


async def homepage(request: Request) -> JSONResponse:
    config = request.state.config
    return JSONResponse({"debug": config("DEBUG", cast=bool, default=False)})


app = Starlette(routes=[Route("/", homepage)], lifespan=lifespan)
