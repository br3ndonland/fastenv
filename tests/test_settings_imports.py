from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


def _check_imports(blocked: tuple[str, ...], assertions: str) -> None:
    script = f"""
import sys
from importlib.abc import MetaPathFinder


class BlockOptionalDependencies(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in {blocked!r}:
            raise ModuleNotFoundError(
                "Blocked optional dependency: " + fullname,
                name=fullname,
            )
        return None


sys.meta_path.insert(0, BlockOptionalDependencies())
""" + textwrap.dedent(assertions)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_core_import_without_either_settings_dependency() -> None:
    _check_imports(
        ("pydantic", "pydantic_core", "starlette"),
        """
        import fastenv
        import fastenv.settings

        assert callable(fastenv.DotEnv)
        assert callable(fastenv.load_dotenv)
        assert fastenv.parse_dotenv("VALUE=example") == {"VALUE": "example"}
        assert not hasattr(fastenv, "BaseSettings")
        assert not hasattr(fastenv, "StarletteConfig")
        assert not hasattr(fastenv.settings, "BaseSettings")
        assert not hasattr(fastenv.settings, "__version__")
        assert "pydantic" not in sys.modules
        assert "starlette" not in sys.modules
        try:
            from fastenv.settings.pydantic_settings import BaseSettings
        except ModuleNotFoundError as error:
            assert error.name == "pydantic"
        else:
            raise AssertionError("Pydantic settings must require Pydantic")
        """,
    )


def test_pydantic_integration_without_starlette() -> None:
    _check_imports(
        ("starlette",),
        """
        import fastenv
        from fastenv import BaseSettings, SettingsConfigDict

        class Settings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="OPTIONAL_IMPORT_TEST_")
            count: int = 0

        assert Settings(count="3").count == 3
        assert not hasattr(fastenv, "StarletteConfig")
        assert "starlette" not in sys.modules
        """,
    )


def test_starlette_integration_without_pydantic() -> None:
    _check_imports(
        ("pydantic", "pydantic_core"),
        """
        import fastenv
        import fastenv.settings
        from fastenv.settings.starlette_config import Config

        assert fastenv.StarletteConfig is Config
        assert Config(environ={"COUNT": "3"})("COUNT", cast=int) == 3
        assert not hasattr(fastenv, "BaseSettings")
        assert "pydantic" not in sys.modules
        assert "pydantic_core" not in sys.modules
        """,
    )


def test_settings_integrations_coexist() -> None:
    _check_imports(
        (),
        """
        import fastenv
        from fastenv import BaseSettings
        from fastenv.settings.starlette_config import Config

        class Settings(BaseSettings):
            count: int = 0

        assert Settings(count="5").count == 5
        assert fastenv.StarletteConfig is Config
        assert Config(environ={"COUNT": "4"})("COUNT", cast=int) == 4
        """,
    )


def test_pydantic_settings_without_unsupported_dependencies() -> None:
    _check_imports(
        ("pydantic_settings", "dotenv", "yaml", "boto3", "botocore", "azure", "google"),
        """
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from fastenv import (
            BaseSettings,
            JsonConfigSettingsSource,
            SettingsConfigDict,
            TomlConfigSettingsSource,
        )

        class Settings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="NO_SDK_TEST_")
            count: int = 0

        os.environ["NO_SDK_TEST_COUNT"] = "7"
        assert Settings().count == 7
        with TemporaryDirectory(dir=os.getenv("TMPDIR", "/tmp")) as directory:
            json_file = Path(directory) / "settings.json"
            json_file.write_text('{"count": 8}')
            assert JsonConfigSettingsSource(Settings, json_file)() == {"count": 8}
            toml_file = Path(directory) / "settings.toml"
            toml_file.write_text("count = 9")
            assert TomlConfigSettingsSource(Settings, toml_file)() == {"count": 9}

        assert not {
            "pydantic_settings", "dotenv", "yaml", "boto3", "botocore", "azure", "google"
        }.intersection(sys.modules)
        """,
    )


def test_missing_pydantic_dependency_is_not_swallowed() -> None:
    _check_imports(
        ("pydantic_core",),
        """
        try:
            import fastenv
        except ModuleNotFoundError as error:
            assert error.name == "pydantic_core"
        else:
            raise AssertionError("A broken Pydantic installation must fail to import")
        """,
    )


def test_public_settings_exports() -> None:
    import fastenv
    import fastenv.settings

    for name in (
        "BaseSettings",
        "DotEnvSettingsSource",
        "EnvSettingsSource",
        "ForceDecode",
        "IncompleteFieldDefinitionWarning",
        "InitSettingsSource",
        "JsonConfigSettingsSource",
        "NestedSecretsSettingsSource",
        "NoDecode",
        "PydanticBaseSettingsSource",
        "PyprojectTomlConfigSettingsSource",
        "SecretsSettingsSource",
        "SettingsConfigDict",
        "SettingsError",
        "TomlConfigSettingsSource",
    ):
        assert name in fastenv.__all__
        assert callable(getattr(fastenv, name))  # pyright: ignore[reportAny]
        assert not hasattr(fastenv.settings, name)
    assert not hasattr(fastenv.settings, "__version__")
