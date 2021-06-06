from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def env_string() -> str:
    """Specify environment variables within a string for testing."""
    return (
        "# this is a comment\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE\n"
        "EMPTY_VARIABLE= \n"
        "PASSWORD_VARIABLE='64w2Q$!&EXAMPLE'\n"
        "USUAL_VARIABLE=value\n"
        "# this is another comment\n"
        "VARIABLE_WITH_QUOTES=\"' just_the_text '\"\n"
        "  VARIABLE_WITH_WHITESPACE = no_whitespace\n"
    )


@pytest.fixture(scope="session")
def env_file(env_string: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create custom temporary .env.testing file."""
    tmp_dir = tmp_path_factory.mktemp("env_file")
    tmp_file = tmp_dir / ".env.testing"
    with open(tmp_file, "x") as f:
        f.write(env_string)
    return Path(tmp_file)


@pytest.fixture(scope="session")
def env_file_empty(env_file: Path) -> Path:
    """Create and load custom temporary .env.testing file with no variables."""
    tmp_file = env_file.parent / ".env.empty"
    with open(tmp_file, "x") as f:
        f.write("\n")
    return Path(tmp_file)
