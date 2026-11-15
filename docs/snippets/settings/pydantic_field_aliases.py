from pydantic import AliasChoices, Field

from fastenv import BaseSettings


class Settings(BaseSettings, env_prefix="SERVICE_"):
    debug: bool = False
    port: int = Field(default=8000, validation_alias=AliasChoices("PORT", "HTTP_PORT"))
