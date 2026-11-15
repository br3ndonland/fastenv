import fastenv
from starlette.datastructures import CommaSeparatedStrings

config = fastenv.StarletteConfig(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
PORT = config("PORT", cast=int, default=8000)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=CommaSeparatedStrings, default="localhost")
