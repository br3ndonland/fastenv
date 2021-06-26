from pathlib import Path

from fastenv.utilities import load_toml


def test_load_toml_with_project_metadata() -> None:
    """Load project metadata from pyproject.toml and verify."""
    project_metadata = load_toml(Path(__file__).parents[1].joinpath("pyproject.toml"))
    assert project_metadata.get("name") == "fastenv"
    assert project_metadata.get("version")
