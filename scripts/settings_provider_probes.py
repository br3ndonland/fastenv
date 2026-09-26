"""Original local-file probes for the public settings provider interfaces."""

# These probes run against two dynamically supplied, independent public APIs.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel


def probe_providers(api: Any, directory: Path) -> dict[str, Any]:
    output: dict[str, Any] = {}

    class Endpoint(BaseModel):
        hostname: str = "localhost"
        port: int = 8000

    class Config(api.BaseSettings):
        endpoint: Endpoint = Endpoint()
        token: str = "unset"

    for suffix, source, base, override in (
        (
            "json",
            api.JsonConfigSettingsSource,
            '{"token":"base","endpoint":{"hostname":"host","port":1}}',
            '{"endpoint":{"port":2}}',
        ),
        (
            "toml",
            api.TomlConfigSettingsSource,
            'token="base"\n[endpoint]\nhostname="host"\nport=1',
            "[endpoint]\nport=2",
        ),
    ):
        first, second = directory / f"base.{suffix}", directory / f"override.{suffix}"
        _ = first.write_text(base)
        _ = second.write_text(override)
        for deep in (False, True):
            output[f"provider-{suffix}-deep-{deep}"] = source(
                Config, [first, second], deep_merge=deep
            )()
        output[f"provider-{suffix}-disabled"] = source(Config, None)()

    toml = directory / "section.toml"
    _ = toml.write_text('[tool.runtime]\ntoken="table"')
    output["provider-toml-table"] = api.TomlConfigSettingsSource(
        Config, toml, toml_table_header=("tool", "runtime")
    )()
    pyproject = directory / "example-pyproject.toml"
    _ = pyproject.write_text('[tool.pydantic-settings]\ntoken="pyproject"')
    output["provider-pyproject-table"] = api.PyprojectTomlConfigSettingsSource(
        Config, pyproject
    )()
    _ = pyproject.write_text('[project]\nname="unrelated"')
    output["provider-pyproject-unrelated"] = api.PyprojectTomlConfigSettingsSource(
        Config, pyproject
    )()

    first_dir, second_dir = directory / "nested-one", directory / "nested-two"
    first_dir.mkdir(exist_ok=True)
    second_dir.mkdir(exist_ok=True)
    _ = (first_dir / "APP_ENDPOINT__HOSTNAME").write_text("host\n")
    _ = (first_dir / "APP_ENDPOINT__PORT").write_text("8001\n")
    _ = (second_dir / "APP_ENDPOINT__PORT").write_text("8002\n")

    class Nested(Config):
        model_config: ClassVar[Any] = api.SettingsConfigDict(
            secrets_dir=[first_dir, second_dir],
            env_prefix="APP_",
            env_nested_delimiter="__",
        )

    output["provider-nested-secrets-priority"] = api.NestedSecretsSettingsSource(
        api.SecretsSettingsSource(Nested)
    )()

    tree = directory / "nested-tree"
    (tree / "endpoint").mkdir(parents=True, exist_ok=True)
    _ = (tree / "endpoint" / "port").write_text("9000")
    output["provider-nested-secrets-tree"] = api.NestedSecretsSettingsSource(
        api.SecretsSettingsSource(Config), secrets_dir=tree, secrets_nested_subdir=True
    )()
    return output
