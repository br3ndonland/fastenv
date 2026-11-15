import fastenv
from starlette.datastructures import Secret

config = fastenv.StarletteConfig(
    environ={"APP_DEBUG": "false", "APP_SECRET_KEY": "example-secret"},
    env_prefix="APP_",
)

DEBUG = config("DEBUG", cast=bool)
SECRET_KEY = config("SECRET_KEY", cast=Secret)
