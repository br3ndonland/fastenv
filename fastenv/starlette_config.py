"""TODO: I'm thinking the Starlette `Config` subclass will be here
"""
from pathlib import Path

from starlette.config import Config as StarletteConfig

from fastenv.utilities import load_toml


class Config(StarletteConfig):
    def load_env_string(self, env_string: str) -> dict[str, str]:
        """Load environment variables from an input string into
        the `file_values` attribute of a Starlette `Config` instance.
        """
        env_string_values = {}
        for line in env_string.splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip(" \"'")
                env_string_values[key] = value
        self.file_values |= env_string_values
        return env_string_values

    def load_pyproject_toml(self, pyproject_path: Path, tool: str = "poetry") -> dict:
        """Load metadata from a pyproject.toml configuration file into
        the `file_values` attribute of a Starlette `Config` instance.
        """
        pyproject_values = load_toml(pyproject_path, tool=tool, uppercase_keys=True)
        self.file_values |= pyproject_values
        return pyproject_values
