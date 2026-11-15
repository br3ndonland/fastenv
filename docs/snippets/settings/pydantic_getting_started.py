# pyright: reportUnannotatedClassAttribute=false
from pydantic import BaseModel

from fastenv import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SERVICE_",
        env_file=".env",
        env_nested_delimiter="__",
    )
    debug: bool = False
    allowed_hosts: list[str] = ["localhost"]
    database: Database = Database()


settings = Settings()
settings.debug
# Output: True
settings.allowed_hosts
# Output: ['localhost', '127.0.0.1']
settings.database
# Output: Database(host='localhost', port=6543)
