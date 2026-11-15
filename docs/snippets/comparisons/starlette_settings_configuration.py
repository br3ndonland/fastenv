import starlette.config

config = starlette.config.Config()
config("FOO_VARIABLE", cast=str, default="baz")
