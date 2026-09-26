# Pydantic settings

`fastenv.settings` provides Pydantic settings models using fastenv to parse dotenv files. It is an original implementation of the public pydantic-settings 2.15.0 API. Neither pydantic-settings nor python-dotenv is a runtime dependency.

Install the optional integration:

```sh
uv add 'fastenv[settings]'
```

Change settings imports to `fastenv.settings`. Continue importing models, fields, aliases, validators, and types from `pydantic`:

```py
from pydantic import BaseModel

from fastenv.settings import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SERVICE_",
        env_file=(".env", ".env.local"),
        env_nested_delimiter="__",
    )
    debug: bool = False
    database: Database = Database()


settings = Settings()
```

For example, `SERVICE_DEBUG=true` becomes a boolean. `SERVICE_DATABASE__PORT=6543` overrides the nested port. A JSON object in `SERVICE_DATABASE` can supply several nested values, and individual nested variables override its matching members.

## Sources and priority

The default order, from highest to lowest priority, is:

1. Command-line arguments, when enabled.
2. Constructor arguments.
3. Process environment variables.
4. Dotenv files, with later files overriding earlier files.
5. Secret files, with later directories overriding earlier directories.
6. Model defaults.

Mappings from different sources are merged recursively. Pydantic validates the merged input and applies field defaults. Default values are validated too. Unknown environment variables are ignored. Unknown constructor and dotenv values are rejected unless `extra="ignore"` or `extra="allow"` is configured.

Per-instance options use the same leading underscore as pydantic-settings. For example, `Settings(_env_file="production.env")` selects another file, and `Settings(_env_file=None)` disables dotenv loading. `Settings(_env_prefix="OTHER_")` changes the prefix for that instance.

The environment and dotenv sources support case sensitivity, aliases, `AliasChoices`, `AliasPath`, prefix targets, nested delimiters and maximum splits, empty-value filtering, null markers, enum names, and JSON decoding. `NoDecode` and `ForceDecode` can be used as `Annotated` metadata. Model configuration can also be supplied through class keywords such as `class Settings(BaseSettings, env_prefix="SERVICE_")`.

## Dotenv parsing and environment isolation

Settings loading never changes `os.environ`. Files are parsed with `fastenv.parse_dotenv`, the same parser used by `fastenv.DotEnv`. This allows independent settings instances to use different files safely, including concurrent loads.

The parser deliberately follows fastenv's format:

- Shell tokenization handles quotes, comments, and whitespace-separated assignments.
- Keys preserve their spelling for case-sensitive settings lookup.
- Variables such as `${HOME}` remain literal text. There is no variable interpolation.
- Bare names without `=` are ignored. An assignment with no value produces an empty string.
- Leading and trailing whitespace and quote characters are stripped according to existing fastenv behavior.
- Invalid shell quoting raises an error.

These parsing details can differ from python-dotenv. Review files that rely on its interpolation or whitespace behavior when migrating.

`parse_dotenv` is also available without Pydantic:

```py
import fastenv

values = fastenv.parse_dotenv("PORT=8000 LABEL='local service'")
assert values == {"PORT": "8000", "LABEL": "local service"}
```

`DotEnv`, `load_dotenv`, and `dotenv_values` retain their existing environment mutation behavior. The settings constructor is synchronous, like Pydantic's model constructor. It can be called inside an event loop without starting another loop. To avoid blocking the loop during file or cloud I/O, use a worker thread:

```py
import anyio

settings = await anyio.to_thread.run_sync(Settings)
```

## Custom and file sources

Override `settings_customise_sources` to add, reorder, or remove sources. The first returned source has the highest priority. A source can be a callable returning a dictionary, or a subclass of `PydanticBaseSettingsSource` with `get_field_value` and `__call__` implementations. Source instances expose `current_state` and `settings_sources_data` while they are being evaluated.

```py
from fastenv.settings import BaseSettings, TomlConfigSettingsSource


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
```

File sources are opt-in through this hook. Setting `toml_file`, `json_file`, or `yaml_file` alone does not insert another source and emits a warning.

| Source | Configuration |
| --- | --- |
| `JsonConfigSettingsSource` | `json_file`, `json_file_encoding` |
| `TomlConfigSettingsSource` | `toml_file`, `toml_table_header` |
| `YamlConfigSettingsSource` | `yaml_file`, `yaml_file_encoding`, `yaml_config_section` |
| `PyprojectTomlConfigSettingsSource` | `pyproject_toml_depth`, `pyproject_toml_table_header` |
| `SecretsSettingsSource` | `secrets_dir`, environment prefix and case settings |
| `NestedSecretsSettingsSource` | Secret directories, nested separators or subdirectories, prefix, case, size and missing-directory policies |

Install `fastenv[yaml]` for YAML. TOML uses Python's standard library. The default pyproject section is `[tool.pydantic-settings]`, preserving the migration contract. Set `pyproject_toml_table_header=("tool", "fastenv")` to use `[tool.fastenv]` instead.

Optional cloud sources use lazily imported SDKs:

| Source                              | Installation extra |
| ----------------------------------- | ------------------ |
| `AWSSecretsManagerSettingsSource`   | `fastenv[aws]`     |
| `AzureKeyVaultSettingsSource`       | `fastenv[azure]`   |
| `GoogleSecretManagerSettingsSource` | `fastenv[gcp]`     |

These sources are also selected through `settings_customise_sources`. Google secret versions can be selected with `Annotated[str, SecretVersion("2")]`, importing `SecretVersion` from `fastenv.settings`. Cloud SDK interactions are covered by mocked tests. Live authentication and service access require validation in the deployment environment.

## Command-line settings

Enable argument parsing explicitly:

```py
from fastenv.settings import BaseSettings, SettingsConfigDict


class Options(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True, cli_implicit_flags=True)
    port: int = 8000
    verbose: bool = False


options = Options()
```

This accepts options such as `--port 9000 --verbose`. A list supplied with `_cli_parse_args=["--port", "9000"]` avoids reading process arguments.

The CLI includes nested options, JSON values, repeated and comma-separated collections, aliases, enum values, boolean flags, positional arguments, subcommands, unknown argument capture, and help configuration. `CliApp` runs model commands, including async commands, and can serialize models back to argument lists. `CliSettingsSource` supports integration with an existing parser.

Public CLI exports include `CLI_SUPPRESS`, `CliApp`, `CliSettingsSource`, `CliSubCommand`, `CliPositionalArg`, `CliImplicitFlag`, `CliExplicitFlag`, `CliDualFlag`, `CliToggleFlag`, `CliSuppress`, `CliUnknownArgs`, `CliMutuallyExclusiveGroup`, and `get_subcommand`.

## Compatibility and verification

The compatibility target is the released **pydantic-settings 2.15.0** public API, imported through `fastenv.settings`. Internal module paths, private methods, exact error text, and exact CLI help formatting are not compatibility contracts. The fastenv package version remains available as `fastenv.settings.__version__`.

The implementation was written from public documentation, signatures, and independently authored behavioral probes. No pydantic-settings implementation or tests were copied. The reference package is only used in an isolated developer command:

```sh
PYTHONPATH=. uv run --no-project --with pydantic-settings==2.15.0 --with PyYAML \
  python scripts/check_settings_compatibility.py
```

This checks public exports and compares settings behavior across both implementations. The regular test suite covers the integration without installing pydantic-settings or python-dotenv. These checks exercise a defined set of behaviors and are not proof of exhaustive equivalence for all Pydantic types or third-party parser implementations.

Background: [fastenv discussion 21](https://github.com/br3ndonland/fastenv/discussions/21), [pydantic-settings](https://github.com/pydantic/pydantic-settings), and the [Pydantic settings documentation](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/).
