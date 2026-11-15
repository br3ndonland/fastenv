# pyright: reportMissingParameterType=false
from fastenv import BaseSettings, TomlConfigSettingsSource


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
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, toml_file="service.toml"),
            dotenv_settings,
            file_secret_settings,
        )
