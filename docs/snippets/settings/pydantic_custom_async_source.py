# pyright: reportExplicitAny=false, reportMissingParameterType=false
from typing import Any

from fastenv import BaseSettings


async def fetch_remote_settings() -> dict[str, Any]:
    return {"port": 9000}  # imagine an HTTP request here


class Settings(BaseSettings):
    port: int = 8000

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (init_settings, env_settings, fetch_remote_settings)
