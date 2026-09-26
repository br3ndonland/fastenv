"""Original behavioral tests for settings composition and fastenv isolation."""

# Settings values intentionally exercise runtime coercion and constructor options
# beyond the signature synthesized by Pydantic's dataclass transform.
# pyright: reportCallIssue=false, reportAny=false, reportExplicitAny=false

from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import AliasChoices, BaseModel, Field, ValidationError
from pydantic.fields import FieldInfo

from fastenv import parse_dotenv
from fastenv.settings.pydantic_settings import BaseSettings, SettingsConfigDict
from fastenv.settings.pydantic_settings_sources import PydanticBaseSettingsSource


def test_parser_is_pure_and_preserves_fastenv_semantics() -> None:
    before = dict(os.environ)
    assert parse_dotenv('export Mixed="hello world" EMPTY= # comment\nBARE') == {
        "MIXED": "hello world",
        "EMPTY": "",
    }
    assert parse_dotenv("Mixed=one", "Mixed=two", case_sensitive=True) == {
        "Mixed": "two"
    }
    assert parse_dotenv("REF='${LITERAL}'") == {"REF": "${LITERAL}"}
    assert dict(os.environ) == before


def test_precedence_and_explicit_dotenv_disable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / "config.env"
    _ = dotenv.write_text("FASTENV_PRIORITY=dotenv\n")
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    _ = (secrets / "FASTENV_PRIORITY").write_text("secret\n")

    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="FASTENV_", env_file=dotenv, secrets_dir=secrets
        )
        priority: str = "default"

    monkeypatch.setenv("FASTENV_PRIORITY", "environment")
    assert Settings(priority="init").priority == "init"
    assert Settings().priority == "environment"
    monkeypatch.delenv("FASTENV_PRIORITY")
    assert Settings().priority == "dotenv"
    assert Settings(_env_file=None).priority == "secret"
    assert Settings(_env_file=None, _secrets_dir=[]).priority == "default"
    assert "FASTENV_PRIORITY" not in os.environ


def test_defaults_are_validated_and_extra_init_rejected() -> None:
    class Invalid(BaseSettings):
        quantity: int = Field(default="bad")  # pyright: ignore[reportAssignmentType]

    with pytest.raises(ValidationError):
        _ = Invalid()

    class Valid(BaseSettings):
        quantity: int = Field(default="7")  # pyright: ignore[reportAssignmentType]

    assert Valid().quantity == 7
    with pytest.raises(ValidationError):
        _ = Valid(unexpected=1)


def test_application_parsed_overrides_merge_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / "config.env"
    _ = dotenv.write_text(
        "FASTENV_APP_DEBUG=true FASTENV_APP_COUNT=20 FASTENV_APP_DATABASE__HOST=file"
    )

    class Database(BaseModel):
        host: str
        port: int

    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="FASTENV_APP_", env_file=dotenv, env_nested_delimiter="__"
        )
        debug: bool
        count: int
        database: Database

    monkeypatch.setenv("FASTENV_APP_DATABASE__PORT", "5432")
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    _ = parser.add_argument("--debug", action=argparse.BooleanOptionalAction)
    _ = parser.add_argument("--count", type=int)

    overrides = vars(parser.parse_args(["--no-debug", "--count", "0"]))
    settings = Settings(**overrides)
    assert settings.model_dump() == {
        "debug": False,
        "count": 0,
        "database": {"host": "file", "port": 5432},
    }
    omitted = Settings(**vars(parser.parse_args([])))
    assert omitted.debug is True
    assert omitted.count == 20


def test_settings_config_class_keywords_and_inheritance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Parent(BaseSettings, env_prefix="FASTENV_PARENT_", case_sensitive=True):
        count: int = 1

    class Child(Parent, env_prefix="FASTENV_CHILD_"):
        pass

    monkeypatch.setenv("FASTENV_PARENT_count", "3")
    monkeypatch.setenv("FASTENV_CHILD_count", "4")
    assert Parent().count == 3
    assert Child().count == 4
    assert Parent.model_config.get("env_prefix") == "FASTENV_PARENT_"
    assert Child.model_config.get("case_sensitive") is True
    assert Child(_env_prefix="FASTENV_PARENT_").count == 3
    assert Child().count == 4


def test_partial_nested_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    class Database(BaseModel):
        host: str = "local"
        port: int = 1

    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="FASTENV_", env_nested_delimiter="__"
        )
        database: Database = Database(host="configured")

    monkeypatch.setenv("FASTENV_DATABASE__PORT", "2")
    assert Settings().database == Database(host="local", port=2)
    assert Settings(_nested_model_default_partial_update=True).database == Database(
        host="configured", port=2
    )
    assert Settings.model_fields["database"].default.host == "configured"


def test_aliases_merge_across_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Database(BaseModel):
        host: str
        port: int

    dotenv = tmp_path / "config.env"
    _ = dotenv.write_text('LEGACY_DB=\'{"host":"file", "port":2}\'\n')

    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=dotenv)
        database: Database = Field(validation_alias=AliasChoices("DB", "LEGACY_DB"))

    monkeypatch.setenv("DB", '{"host":"environment"}')
    assert Settings(LEGACY_DB={"port": 3}).database == Database(
        host="environment", port=3
    )


def test_custom_sources_priority_state_and_removal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Computed(PydanticBaseSettingsSource):
        def get_field_value(
            self, field: FieldInfo, field_name: str
        ) -> tuple[Any, str, bool]:
            return None, field_name, False

        def __call__(self) -> dict[str, Any]:
            assert self.current_state == {"count": "4"}
            assert self.settings_sources_data["EnvSettingsSource"] == {"count": "4"}
            return {"double": int(self.current_state["count"]) * 2}

    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="FASTENV_"
        )
        count: int
        double: int

        @classmethod
        def settings_customise_sources(
            cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            computed = Computed(settings_cls)
            assert computed.get_field_value(
                settings_cls.model_fields["count"], "count"
            ) == (None, "count", False)
            return sources["env_settings"], computed

    monkeypatch.setenv("FASTENV_COUNT", "4")
    assert Settings(count=20).model_dump() == {"count": 4, "double": 8}


def test_callable_source_and_no_sources() -> None:
    class Settings(BaseSettings):
        enabled: bool = False

        @classmethod
        def settings_customise_sources(
            cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
        ) -> tuple[Any, ...]:
            return (lambda: {"enabled": "yes"},)

    class Defaults(Settings):
        @classmethod
        def settings_customise_sources(
            cls, settings_cls: type[BaseSettings], *_args: Any, **sources: Any
        ) -> tuple[Any, ...]:
            return ()

    assert Settings().enabled is True
    assert Defaults(enabled=True).enabled is False


def test_model_validation_and_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="FASTENV_"
        )
        count: int = 0

    monkeypatch.setenv("FASTENV_COUNT", "3")
    settings = Settings.model_validate({})
    assert settings.count == 3
    assert Settings.model_validate_json("{}").count == 3
    monkeypatch.setenv("FASTENV_COUNT", "4")
    settings.__init__()
    assert settings.count == 4
    assert Settings.model_json_schema()["properties"]["count"]["type"] == "integer"


def test_concurrent_loads_leave_environment_unchanged(tmp_path: Path) -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="FASTENV_CONCURRENT_"
        )
        value: str

    files = [tmp_path / f"{index}.env" for index in range(12)]
    for index, file in enumerate(files):
        _ = file.write_text(f"FASTENV_CONCURRENT_VALUE=value-{index}\n")
    before = dict(os.environ)

    def load(file: Path) -> str:
        return Settings(_env_file=file).value

    with ThreadPoolExecutor(max_workers=4) as executor:
        actual = list(executor.map(load, files))
    assert actual == [f"value-{index}" for index in range(12)]
    assert dict(os.environ) == before


@pytest.mark.anyio
async def test_settings_inside_running_event_loop(tmp_path: Path) -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_prefix="FASTENV_ASYNC_"
        )
        value: int

    file = tmp_path / "async.env"
    _ = file.write_text("FASTENV_ASYNC_VALUE=21\n")
    assert Settings(_env_file=file).value == 21


def test_self_can_be_a_field() -> None:
    class Settings(BaseSettings):
        self: str

    assert Settings(self="example").self == "example"


def test_source_field_lookup_hook() -> None:
    from fastenv.settings.pydantic_settings_sources import InitSettingsSource

    class Settings(BaseSettings):
        enabled: bool = False

    source = InitSettingsSource(Settings, {"enabled": True})
    assert source.get_field_value(Settings.model_fields["enabled"], "enabled") == (
        True,
        "enabled",
        False,
    )


@pytest.mark.parametrize("values", [{}, {"nested": {}}, {"nested": {"number": 4}}])
def test_unchanged_partial_defaults_remain_unset(values: dict[str, Any]) -> None:
    class Child(BaseModel):
        number: int = 1
        text: str = "default"

    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            nested_model_default_partial_update=True
        )
        nested: Child = Child(number=4)

    settings = Settings(**values)
    assert settings.nested.number == 4
    assert settings.nested.model_fields_set == {"number"}
    assert settings.model_fields_set == set()
    assert settings.model_dump(exclude_unset=True) == {}
    changed = Settings(nested={"number": 5})  # pyright: ignore[reportArgumentType]
    assert changed.model_fields_set == {"nested"}


def test_unused_file_configuration_warns() -> None:
    class Settings(BaseSettings):
        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            json_file="unused.json"
        )

    with pytest.warns(UserWarning, match="json_file.*JsonConfigSettingsSource"):
        _ = Settings()


def test_invalid_alias_field_name_is_not_discarded() -> None:
    class Settings(BaseSettings):
        value: int = Field(alias="ALIAS")

    with pytest.raises(ValidationError) as error:
        _ = Settings(ALIAS=1, value=2)
    assert error.value.errors()[0]["type"] == "extra_forbidden"
    assert error.value.errors()[0]["loc"] == ("value",)
    assert Settings(alias=3).value == 3
    assert Settings(alias=3, _case_sensitive=True).value == 3

    class Sensitive(Settings, case_sensitive=True):
        pass

    with pytest.raises(ValidationError):
        _ = Sensitive(alias=3)
