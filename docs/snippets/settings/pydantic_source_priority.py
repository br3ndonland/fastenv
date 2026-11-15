# pyright: reportUndefinedVariable=false, reportUnknownMemberType=false
import os

os.environ["SERVICE_DATABASE__PORT"] = "7000"

Settings().database.port
# Output: 7000
Settings(debug=False).debug
# Output: False
