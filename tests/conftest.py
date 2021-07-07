import pathlib

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
def env_file(env_str: str, tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """Create custom temporary .env.testing file."""
    tmp_dir = tmp_path_factory.mktemp("env_files")
    tmp_file = tmp_dir / ".env.testing"
    with open(tmp_file, "x") as f:
        f.write(env_str)
    return pathlib.Path(tmp_file)


@pytest.fixture(scope="session")
def env_file_empty(env_file: pathlib.Path) -> pathlib.Path:
    """Create and load custom temporary .env.testing file with no variables."""
    tmp_file = env_file.parent / ".env.empty"
    with open(tmp_file, "x") as f:
        f.write("\n")
    return pathlib.Path(tmp_file)
