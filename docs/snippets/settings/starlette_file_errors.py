import fastenv

config = fastenv.StarletteConfig(
    env_file=[".env", ".env.local"],
    toml_file="pyproject.toml",
    raise_exceptions=False,
)
DEBUG = config("DEBUG", cast=bool, default=False)
