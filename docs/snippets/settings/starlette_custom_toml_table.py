import fastenv

config = fastenv.StarletteConfig(
    toml_file="settings.toml",
    toml_table="application",
)

DEBUG = config("DEBUG", cast=bool)
PORT = config("PORT", cast=int)
DATABASE = config("DATABASE")
print(DATABASE)
# Output: {'host': 'localhost', 'port': 5432}
