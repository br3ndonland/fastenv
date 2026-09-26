"""Compare original behavior probes with the released public API.

Run from the repository root in a separate virtual environment containing
fastenv[settings] and pydantic-settings==2.15.0:
    python -m scripts.check_settings_compatibility

See docs/settings.md for installation instructions.
The reference package is an isolated development oracle, never a fastenv dependency.
This script uses only public imports and model behavior, not implementation source.
"""

# The same probes intentionally accept two dynamically imported public APIs.
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import contextlib
import importlib
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, ClassVar
from unittest.mock import patch

from pydantic import AliasChoices, AliasPath, BaseModel, Field, Json, ValidationError
from scripts.settings_cli_probes import probe_cli
from scripts.settings_provider_probes import probe_providers


def probe(api: Any, directory: Path) -> dict[str, Any]:
    output: dict[str, Any] = {}

    def record(label: str, model: Any, **kwargs: Any) -> None:
        try:
            output[label] = model(**kwargs).model_dump(mode="json")
        except ValidationError as error:
            output[label] = [(item["type"], item["loc"]) for item in error.errors()]
        except (ValueError, TypeError, SystemExit) as error:
            output[label] = type(error).__name__

    class Database(BaseModel):
        host: str = "localhost"
        port: int = 11

    class Basic(api.BaseSettings):
        model_config: ClassVar[Any] = api.SettingsConfigDict(
            env_prefix="APP_", env_nested_delimiter="__"
        )
        number: int = 1
        enabled: bool = False
        database: Database = Database(host="preset")
        items: list[int] = Field(default_factory=list[int])

    record("defaults", Basic)
    record("init", Basic, number="5", enabled="yes")
    record("extra-init", Basic, typo=1)
    record("init-case-insensitive", Basic, NUMBER=3)
    record("init-case-sensitive", Basic, NUMBER=3, _case_sensitive=True)
    with patch.dict(os.environ, {"APP_NUMBER": "2", "APP_ENABLED": "true"}, clear=True):
        record("environment", Basic)
        record("init-priority", Basic, number=3)
        record("prefix-override", Basic, _env_prefix="ALT_")
    with patch.dict(os.environ, {"APP_NUMBER": "", "APP_ITEMS": "[3,4]"}, clear=True):
        record("empty-invalid", Basic)
        record("empty-ignore", Basic, _env_ignore_empty=True)
    with patch.dict(
        os.environ,
        {"APP_DATABASE": '{"host":"remote","port":2}', "APP_DATABASE__PORT": "3"},
        clear=True,
    ):
        record("nested-json", Basic)
        record("nested-init-merge", Basic, database={"host": "init"})
    with patch.dict(os.environ, {"APP_DATABASE__PORT": "3"}, clear=True):
        record("partial-default-off", Basic)
        record("partial-default-on", Basic, _nested_model_default_partial_update=True)
    with patch.dict(os.environ, {"APP_ITEMS": "3,4"}, clear=True):
        record("invalid-json", Basic)
    partial_inputs: tuple[dict[str, Any], ...] = (
        {},
        {"database": {}},
        {"database": {"host": "preset"}},
        {"database": {"port": 7}},
    )
    for values in partial_inputs:
        instance = Basic(_nested_model_default_partial_update=True, **values)
        output[f"partial-default-fields-{values}"] = {
            "fields": sorted(instance.model_fields_set),
            "nested_fields": sorted(instance.database.model_fields_set),
            "unset": instance.model_dump(exclude_unset=True),
        }

    class Aliased(api.BaseSettings):
        model_config: ClassVar[Any] = api.SettingsConfigDict(
            env_prefix="APP_", populate_by_name=True
        )
        number: int = Field(1, validation_alias=AliasChoices("NUM", "NUMBER"))
        nested: int = Field(0, validation_alias=AliasPath("PATH", 1))

    for key in ("NUM", "NUMBER", "APP_NUMBER"):
        with patch.dict(os.environ, {key: "5", "PATH": '["ignored",9]'}, clear=True):
            record(f"alias-{key}", Aliased)
            record(f"alias-{key}-init", Aliased, number=7)
    with patch.dict(os.environ, {"APP_NUM": "6"}, clear=True):
        record("prefix-alias-target", Aliased, _env_prefix_target="alias")
        record("prefix-all-target", Aliased, _env_prefix_target="all")
    for case_sensitive in (True, False):
        with patch.dict(os.environ, {"app_number": "4"}, clear=True):
            record(f"case-{case_sensitive}", Basic, _case_sensitive=case_sensitive)

    class Optional(api.BaseSettings):
        choice: int | None = 1
        data: list[int] | str = "default"
        parsed: Json[list[int]] = "[0]"  # pyright: ignore[reportAssignmentType]
        forced: Annotated[list[int], api.ForceDecode] = Field(default_factory=list[int])

    class InvalidAlias(api.BaseSettings):
        value: int = Field(alias="ALIAS")

    record("alias-invalid-name", InvalidAlias, ALIAS=1, value=2)
    record("alias-lowercase-init", InvalidAlias, alias=3)
    record("alias-case-sensitive-init", InvalidAlias, alias=3, _case_sensitive=True)
    record(
        "cli-env-none-marker",
        Optional,
        _env_parse_none_str="nil",
        _cli_parse_args=["--choice", "nil"],
    )

    with patch.dict(
        os.environ,
        {"CHOICE": "nil", "DATA": "text", "PARSED": "[7]", "FORCED": "[8]"},
        clear=True,
    ):
        record("null-union-json", Optional, _env_parse_none_str="nil")

    dotenv = directory / "config.env"
    _ = dotenv.write_text("APP_NUMBER=7\nAPP_ENABLED=true\n", encoding="utf-8")
    second = directory / "second.env"
    _ = second.write_text("APP_NUMBER=8\n", encoding="utf-8")
    record("dotenv", Basic, _env_file=dotenv)
    record("dotenv-files", Basic, _env_file=[dotenv, second])
    record("dotenv-missing", Basic, _env_file=directory / "absent")
    with patch.dict(os.environ, {"APP_NUMBER": "9"}, clear=True):
        record("dotenv-env-priority", Basic, _env_file=dotenv)
    _ = dotenv.write_text("APP_TYPO=1\nOTHER=2\n", encoding="utf-8")
    record("dotenv-extras-forbid", Basic, _env_file=dotenv)
    for extra in ("allow", "ignore"):
        for filtering in (None, "only_existing", "match_prefix"):

            class Filtered(api.BaseSettings):
                model_config: ClassVar[Any] = api.SettingsConfigDict(
                    env_prefix="APP_", extra=extra, dotenv_filtering=filtering
                )
                number: int = 0

            record(f"dotenv-{extra}-{filtering}", Filtered, _env_file=dotenv)

    secrets = directory / "secrets"
    secrets.mkdir(exist_ok=True)
    _ = (secrets / "APP_NUMBER").write_text(" 42\n", encoding="utf-8")
    record("secrets", Basic, _secrets_dir=secrets)
    record("secrets-init-priority", Basic, _secrets_dir=secrets, number=43)

    class Customized(Basic):
        @classmethod
        def settings_customise_sources(
            cls, settings_cls: Any, **sources: Any
        ) -> tuple[Any, ...]:
            return (
                sources["env_settings"],
                lambda: {"enabled": True},
                sources["init_settings"],
            )

    with patch.dict(os.environ, {"APP_NUMBER": "9"}, clear=True):
        record("custom-order", Customized, number=10)

    for args in (
        [],
        ["--number", "5"],
        ["--items", "1,2"],
        ["--items", "[1,2]", "--items", "3"],
        ["--database.host", "cli", "--database.port", "80"],
        ["--database", '{"host":"json","port":10}', "--database.port", "81"],
    ):
        record(f"cli-{args}", Basic, _cli_parse_args=args)
    record("cli-priority", Basic, _cli_parse_args=["--number", "10"], number=11)
    record("cli-flag", Basic, _cli_parse_args=["--enabled"], _cli_implicit_flags=True)
    record(
        "cli-no-flag", Basic, _cli_parse_args=["--no-enabled"], _cli_implicit_flags=True
    )
    record(
        "cli-unknown", Basic, _cli_parse_args=["--unknown"], _cli_exit_on_error=False
    )
    record(
        "cli-ignore-unknown",
        Basic,
        _cli_parse_args=["--unknown"],
        _cli_ignore_unknown_args=True,
    )
    output.update(probe_providers(api, directory))
    output.update(probe_cli(api))
    return output


def main() -> None:
    reference = importlib.import_module("pydantic_settings")
    replacement = importlib.import_module("fastenv.settings")
    assert reference.__version__ == "2.15.0", "Use the pinned reference release"
    intentionally_omitted = {
        "AWSSecretsManagerSettingsSource",
        "AzureKeyVaultSettingsSource",
        "GoogleSecretManagerSettingsSource",
        "YamlConfigSettingsSource",
    }
    missing = set(reference.__all__) - set(replacement.__all__)
    assert missing == intentionally_omitted, (
        f"Unexpected public API differences: {missing}"
    )
    with (
        TemporaryDirectory(
            prefix="fastenv-compat-", dir=os.getenv("TMPDIR", "/tmp")
        ) as temporary,
        patch.dict(os.environ, {}, clear=True),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        expected = probe(reference, Path(temporary))
        actual = probe(replacement, Path(temporary))
    failures = {
        key: {"reference": value, "fastenv": actual.get(key)}
        for key, value in expected.items()
        if actual.get(key) != value
    }
    for key, value in failures.items():
        print(f"FAIL {key}: {value}")
    print(
        f"{len(expected) - len(failures)}/{len(expected)} behavioral probes match pydantic-settings 2.15.0"
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
