import os
import starlette.config

os.environ.get("FOO_VARIABLE")
starlette.config.environ["FOO_VARIABLE"] = "bar"
os.environ.get("FOO_VARIABLE")
# Output: 'bar'
config = starlette.config.Config()
config("FOO_VARIABLE", cast=str, default="baz")
# Output: 'bar'
starlette.config.environ["FOO_VARIABLE"] = "foo"
# Raises: starlette.config.EnvironError: Attempting to set environ['FOO_VARIABLE'], but the value has already been read.
os.environ["FOO_VARIABLE"] = "foo"
os.environ["FOO_VARIABLE"]
# Output: 'foo'
starlette.config.environ["FOO_VARIABLE"]
# Output: 'foo'
config("FOO_VARIABLE", cast=str, default="baz")
# Output: 'foo'
