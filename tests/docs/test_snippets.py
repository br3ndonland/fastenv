# pyright: reportAny=false, reportExplicitAny=false
from __future__ import annotations

import ast
import re
from collections.abc import Generator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, cast

import anyio
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "snippets"


def display_result(value: object) -> None:
    if value is not None:
        print(repr(value))


@contextmanager
def expect_output(kind: str, expected: str, location: str) -> Generator[None]:
    if kind == "Raises":
        with pytest.raises(Exception) as error:
            yield
        cls = type(error.value)
        assert f"{cls.__module__}.{cls.__qualname__}: {error.value}" == expected, (
            location
        )
    else:
        with redirect_stdout(StringIO()) as stdout:
            yield
        assert stdout.getvalue() == expected + "\n", location


def execute_example(source: str, filename: str, scope: dict[str, Any]) -> None:
    """Check annotated statements as they run, including inside functions."""
    expectations = {
        line: match.groups()
        for line, text in enumerate(source.splitlines(), 1)
        if (match := re.fullmatch(r"\s*# (Output|Raises): (.+)", text))
    }

    class CheckOutput(ast.NodeTransformer):
        def generic_visit(self, node: ast.AST) -> ast.AST:
            node = super().generic_visit(node)
            if not isinstance(node, ast.stmt) or node.end_lineno is None:
                return node
            line = node.end_lineno + 1
            if line not in expectations:
                return node
            kind, expected = expectations.pop(line)
            location = f"{filename}:{line}"
            if kind == "Output":
                assert isinstance(node, ast.Expr), location
                node.value = ast.Call(
                    func=ast.Name(id="__display_result__", ctx=ast.Load()),
                    args=[node.value],
                    keywords=[],
                )
            guard = ast.Call(
                func=ast.Name(id="__expect_output__", ctx=ast.Load()),
                args=[
                    ast.Constant(value=value) for value in (kind, expected, location)
                ],
                keywords=[],
            )
            return ast.copy_location(
                ast.With(items=[ast.withitem(context_expr=guard)], body=[node]),
                node,
            )

    tree = CheckOutput().visit(ast.parse(source, filename=filename))
    assert not expectations, (
        f"{filename}: output comments without statements: {expectations}"
    )
    scope.update(__display_result__=display_result, __expect_output__=expect_output)
    exec(
        compile(ast.fix_missing_locations(tree), filename, "exec", dont_inherit=True),
        scope,
    )


def run_example(
    page: str, name: str, namespace: dict[str, Any] | None = None
) -> dict[str, Any]:
    path = EXAMPLES / page / f"{name}.py"
    scope: dict[str, Any] = {"__name__": "documentation_example"}
    if namespace:
        scope.update(namespace)
    execute_example(path.read_text(), str(path), scope)
    return scope


def test_readme_quickstart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for key in ("EXAMPLE_VARIABLE", "ANOTHER_VARIABLE", "I_THINK_FASTENV_IS", "DEBUG"):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    text = (ROOT / "docs" / "index.md").read_text()
    blocks = cast(list[str], re.findall(r"(?ms)^```py\n(.*?)^```", text))
    assert len(blocks) == 2
    scope: dict[str, Any] = {"__name__": "documentation_example"}
    for block in blocks:
        execute_example(block, "docs/index.md", scope)
    assert (tmp_path / ".env").is_file()
    with TestClient(scope["app"]) as client:
        assert client.get("/settings").json() == {
            "example_variable": "example_value",
            "i_think_fastenv_is": "awesome",
            "debug": False,
        }


@pytest.mark.parametrize(
    "name",
    [
        "creating_dotenv",
        "os_environ_style_api",
        "creating_dotenv_with_variables",
        "getting_variables",
        "setting_variables",
        "getting_and_setting_variables",
        "deleting_variables",
        "handling_non_string_values",
    ],
)
def test_environment_examples(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "EXAMPLE_VARIABLE",
        "KEY1",
        "KEY2",
        "KEY3",
        "KEY4",
        "KEY5",
        "INCORRECT_TYPE",
    ):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    scope = run_example("environment", name)
    expected = {
        "creating_dotenv": {},
        "os_environ_style_api": {},
        "creating_dotenv_with_variables": {
            "KEY1": "value1",
            "KEY2": "value2",
            "KEY3": "value3",
            "KEY4": "value4",
        },
        "getting_variables": {"KEY1": "value1"},
        "setting_variables": {
            "KEY1": "value1",
            "KEY2": "value2",
            "KEY3": "value3",
            "KEY4": "value4",
            "KEY5": "value5",
        },
        "getting_and_setting_variables": {
            "KEY1": "value1",
            "KEY2": "value2",
            "KEY3": "value3",
            "KEY4": "value4",
        },
        "deleting_variables": {},
        "handling_non_string_values": {"INCORRECT_TYPE": "[1, 2, 3]"},
    }
    assert dict(scope["dotenv"]) == expected[name]


@pytest.mark.parametrize(
    "name",
    ["loading_dotenv_file", "loading_multiple_dotenv_files", "dumping_dotenv_file"],
)
def test_dotenv_examples(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC_EXAMPLE", "")
    monkeypatch.delenv("DOC_EXAMPLE")
    _ = (tmp_path / ".env").write_text("DOC_EXAMPLE=base\n")
    _ = (tmp_path / ".env.override").write_text("DOC_EXAMPLE=override\n")
    scope = run_example("dotenv", name)
    if name == "loading_dotenv_file":
        result = anyio.run(scope["load_my_dotenv"])
        assert result["DOC_EXAMPLE"] == "base"
    elif name == "loading_multiple_dotenv_files":
        result = anyio.run(scope["load_my_dotenvs"], ".env", ".env.override")
        assert result["DOC_EXAMPLE"] == "override"
    else:
        result = anyio.run(scope["load_and_dump_my_dotenvs"], ".env", ".env.override")
        assert result["DOC_EXAMPLE"] == "override"
        assert "DOC_EXAMPLE=override" in (tmp_path / ".env.dump").read_text()


def test_every_snippet_is_referenced() -> None:
    references: list[str] = []
    for page in (ROOT / "docs").glob("*.md"):
        references.extend(
            re.findall(r'--8<-- "(docs/snippets/[^\":]+)(?::2:)?"', page.read_text())
        )
    paths = {path.relative_to(ROOT).as_posix() for path in EXAMPLES.rglob("*.py")}
    assert set(references) == paths
    assert len(references) == len(paths)
    for path in paths:
        _ = ast.parse((ROOT / path).read_text(), filename=path)


def test_pydantic_settings_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "SERVICE_DEBUG",
        "SERVICE_ALLOWED_HOSTS",
        "SERVICE_DATABASE__PORT",
        "PORT",
        "HTTP_PORT",
    ):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    _ = (tmp_path / ".env").write_text(
        'SERVICE_DEBUG=true\nSERVICE_ALLOWED_HOSTS=\'["localhost", "127.0.0.1"]\'\nSERVICE_DATABASE__PORT=6543\n'
    )
    scope = run_example("settings", "pydantic_getting_started")
    assert scope["settings"].model_dump() == {
        "debug": True,
        "allowed_hosts": ["localhost", "127.0.0.1"],
        "database": {"host": "localhost", "port": 6543},
    }
    _ = run_example("settings", "pydantic_async_loading", scope)
    _ = run_example("settings", "pydantic_source_priority", scope)
    assert scope["Settings"]().database.port == 7000
    assert scope["Settings"](debug=False).debug is False
    _ = run_example("settings", "pydantic_instance_options", scope)
    aliases = run_example("settings", "pydantic_field_aliases")
    monkeypatch.setenv("HTTP_PORT", "1234")
    assert aliases["Settings"]().port == 1234
    _ = run_example("settings", "pydantic_dotenv_parsing")
    _ = (tmp_path / "service.toml").write_text("port = 8765\n")
    custom = run_example("settings", "pydantic_toml_source")
    assert custom["Settings"]().port == 8765
    remote = run_example("settings", "pydantic_custom_async_source")
    assert anyio.run(remote["Settings"].load).port == 9000
    monkeypatch.setattr("sys.argv", ["example", "--port", "4321"])
    cli = run_example("settings", "pydantic_command_line_arguments")
    assert cli["settings"].port == 4321


def test_starlette_settings_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "DEBUG",
        "PORT",
        "ALLOWED_HOSTS",
        "NAME",
        "VERSION",
        "REQUIRES-PYTHON",
        "DEPENDENCIES",
    ):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    _ = (tmp_path / ".env").write_text(
        "DEBUG=false\nPORT=8000\nALLOWED_HOSTS=localhost,127.0.0.1\n"
    )
    _ = (tmp_path / ".env.local").write_text("PORT=9000\n")
    _ = (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="example-app"\nversion="1.0.0"\nrequires-python=">=3.11"\ndependencies=["fastenv[starlette]"]\n'
    )
    _ = (tmp_path / "settings.toml").write_text(
        '[application]\ndebug=false\nport=8000\n[application.database]\nhost="localhost"\nport=5432\n'
    )
    first = run_example("settings", "starlette_load_file_in_constructor")
    assert (first["DEBUG"], first["PORT"], list(first["ALLOWED_HOSTS"])) == (
        False,
        8000,
        ["localhost", "127.0.0.1"],
    )
    assert (
        run_example("settings", "starlette_load_multiple_files")["config"](
            "PORT", cast=int
        )
        == 9000
    )
    assert (
        anyio.run(run_example("settings", "starlette_async_loading")["load_settings"])(
            "PORT", cast=int
        )
        == 9000
    )
    assert run_example("settings", "starlette_source_precedence")["PORT"] == 9000
    assert (
        run_example("settings", "starlette_direct_import")["StarletteConfig"]
        is not None
    )
    metadata = run_example("settings", "starlette_project_metadata")
    assert (
        metadata["APP_NAME"],
        metadata["APP_VERSION"],
        metadata["REQUIRES_PYTHON"],
        metadata["DEPENDENCIES"],
    ) == ("example-app", "1.0.0", ">=3.11", ["fastenv[starlette]"])
    values = run_example("settings", "starlette_custom_toml_table")
    assert (values["DEBUG"], values["PORT"], values["DATABASE"]) == (
        False,
        8000,
        {"host": "localhost", "port": 5432},
    )
    values = run_example("settings", "starlette_environment_prefix")
    assert values["DEBUG"] is False
    assert str(values["SECRET_KEY"]) == "example-secret"
    assert run_example("settings", "starlette_file_errors")["DEBUG"] is False
    with TestClient(
        run_example("settings", "starlette_application_startup")["app"]
    ) as client:
        assert client.get("/").json() == {"debug": False}


def test_cloud_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import fastenv

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC_CLOUD", "")
    monkeypatch.delenv("DOC_CLOUD")
    calls: list[tuple[Any, ...]] = []

    class Client:
        def __init__(self, config: Any) -> None:
            calls.append(("config", config))

        async def upload(self, path: str, source: Any) -> str:
            calls.append(("upload", path, source))
            return "uploaded"

        async def download(self, path: str, destination: Any = None) -> anyio.Path:
            calls.append(("download", path, destination))
            output = anyio.Path(destination or path)
            _ = await output.write_text(
                "DOC_CLOUD=" + ("custom" if path == ".env.custom" else "common") + "\n"
            )
            return output

    def make_config(**kwargs: object) -> dict[str, object]:
        return kwargs

    monkeypatch.setattr(fastenv, "ObjectStorageConfig", make_config)
    monkeypatch.setattr(fastenv, "ObjectStorageClient", Client)
    upload = run_example("cloud_object_storage", "uploading_dotenv_file")
    assert (
        anyio.run(upload["upload_my_dotenv"], "bucket.example", "region") == "uploaded"
    )
    assert ("upload", "uploads/fastenv-docs/.env", ".env") in calls
    download = run_example("cloud_object_storage", "downloading_dotenv_file")
    result = anyio.run(download["download_my_dotenv"], "bucket.example", "region")
    assert str(result) == ".env.download"
    assert (tmp_path / ".env.download").read_text() == "DOC_CLOUD=common\n"
    combined = run_example("cloud_object_storage", "downloading_multiple_dotenv_files")
    result = anyio.run(combined["download_my_dotenvs"], "bucket.example", "region")
    assert result["DOC_CLOUD"] == "custom"


def test_comparison_examples(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    import starlette.config

    for key in ("BOOLEAN_SETTING", "INTEGER_SETTING", "STRING_SETTING", "FOO_VARIABLE"):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    _ = run_example("comparisons", "pydantic_settings_configuration")

    monkeypatch.setattr(starlette.config.environ, "_has_been_read", set[str]())
    assert (
        run_example("comparisons", "starlette_settings_configuration")["config"](
            "FOO_VARIABLE", default="baz"
        )
        == "baz"
    )
    assert (
        run_example("comparisons", "starlette_type_casting")["config"](
            "BOOLEAN_SETTING", cast=bool, default="false"
        )
        is False
    )
    monkeypatch.setattr(starlette.config.environ, "_has_been_read", set[str]())
    scope = run_example("comparisons", "starlette_environment_protection")
    assert os.environ["FOO_VARIABLE"] == "foo"
    assert scope["config"]("FOO_VARIABLE") == "foo"
