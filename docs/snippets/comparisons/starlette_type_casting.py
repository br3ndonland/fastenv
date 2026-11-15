bool("false")
# Output: True
import starlette.config

config = starlette.config.Config()
config("BOOLEAN_SETTING", cast=bool, default="false")
# Output: False
