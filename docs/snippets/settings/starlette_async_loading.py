import fastenv


async def load_settings() -> fastenv.StarletteConfig:
    config = await fastenv.StarletteConfig.load(env_file=[".env", ".env.local"])
    port = config("PORT", cast=int, default=8000)
    print(f"Using port {port}")
    return config
