from __future__ import annotations

import anyio
import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Specify the back-end for pytest to use when running async functions
    with [AnyIO](https://anyio.readthedocs.io/en/stable/testing.html).
    """
    return "asyncio"


@pytest.fixture(scope="session")
def env_str() -> str:
    """Specify environment variables within a string for testing."""
    return (
        "# comment\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE\n"
        "CSV_VARIABLE=comma,separated,value\n"
        "EMPTY_VARIABLE= \n"
        "# comment\n"
        "INLINE_COMMENT=no_comment  # inline comment  \n"
        'JSON_EXAMPLE=\'{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}\'\n'
        "PASSWORD='64w2Q$!&,,[EXAMPLE'\n"
        "QUOTES_AND_WHITESPACE=\"' text and spaces '\"\n"
        "URI_TO_DIRECTORY=~/dev\n"
        "URI_TO_S3_BUCKET=s3://mybucket/.env\n"
        "URI_TO_SQLITE_DB=sqlite:////path/to/db.sqlite\n"
        "URL_EXAMPLE=https://start.duckduckgo.com/\n"
    )


@pytest.fixture(scope="session")
def env_str_unsorted() -> str:
    """Specify unsorted environment variables within a string for testing."""
    return "KEY3=value3\nKEY1=value1\nKEY2=value2\n"


@pytest.fixture(scope="session")
def env_str_multi() -> tuple[str, ...]:
    """Specify environment variables within multiple strings for testing."""
    return tuple(
        (
            f"AWS_ACCESS_KEY_ID=AKIAIOSMULTI{i}EXAMPLE\n"
            f"AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPMULTI{i}EXAMPLE\n"
            f"CSV_VARIABLE=multi,{i},example\n"
            f"MULTI_{i}_VARIABLE=multi_{i}_value"
        )
        for i in range(3)
    )


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file(
    env_str: str, tmp_path_factory: pytest.TempPathFactory
) -> anyio.Path:
    """Create .env.testing file with environment variables."""
    tmp_dir = tmp_path_factory.mktemp("env_files")
    tmp_file = anyio.Path(tmp_dir) / ".env.testing"
    await tmp_file.write_text(env_str)
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_unsorted(env_file: anyio.Path, env_str_unsorted: str) -> anyio.Path:
    """Create .env file with unsorted environment variables."""
    tmp_file = env_file.parent / ".env.unsorted"
    await tmp_file.write_text(env_str_unsorted)
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_empty(env_file: anyio.Path) -> anyio.Path:
    """Create .env file with no variables."""
    tmp_file = env_file.parent / ".env.empty"
    await tmp_file.write_text("\n")
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_child_dir(env_file: anyio.Path) -> anyio.Path:
    """Create child directories to test `find_dotenv`."""
    starting_dir = anyio.Path(env_file.parent) / "child1" / "child2" / "child3"
    await starting_dir.mkdir(parents=True, exist_ok=False)
    return starting_dir


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_files_in_same_dir(
    env_file: anyio.Path,
    env_str_multi: tuple[str, ...],
) -> list[anyio.Path]:
    """Create multiple .env files in a single directory to test `load_dotenv`."""
    env_files: list[anyio.Path] = [env_file]
    for i, env_str in enumerate(env_str_multi):
        new_file = env_file.parent / f".env.child{i}"
        await new_file.write_text(env_str)
        env_files.append(new_file)
    return env_files


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_files_in_child_dirs(
    env_file_child_dir: anyio.Path,
    env_str_multi: tuple[str, ...],
) -> list[anyio.Path]:
    """Create multiple .env files in child directories to test `load_dotenv`."""
    env_files: list[anyio.Path] = []
    for i, env_str in enumerate(env_str_multi):
        new_file = env_file_child_dir.parents[i] / f".env.child{i}"
        await new_file.write_text(env_str)
        env_files.append(new_file)
    return env_files
