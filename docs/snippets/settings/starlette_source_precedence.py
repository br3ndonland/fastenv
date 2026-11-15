import fastenv

config = fastenv.StarletteConfig(
    env_file=[".env", ".env.local"],
    toml_file="pyproject.toml",
)
PORT = config("PORT", cast=int, default=8000)
