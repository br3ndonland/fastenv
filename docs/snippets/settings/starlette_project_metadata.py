import fastenv

config = fastenv.StarletteConfig(toml_file="pyproject.toml")

APP_NAME = config("NAME")
APP_VERSION = config("VERSION")
REQUIRES_PYTHON = config("REQUIRES-PYTHON")
DEPENDENCIES = config("DEPENDENCIES")
