import os
import fastenv

dotenv = fastenv.DotEnv()
dotenv["EXAMPLE_VARIABLE"] = "example_value"
dotenv["EXAMPLE_VARIABLE"]
# Output: 'example_value'
os.environ["EXAMPLE_VARIABLE"]
# Output: 'example_value'
del dotenv["EXAMPLE_VARIABLE"]
dotenv.getenv("EXAMPLE_VARIABLE", "variable_was_deleted")
# Output: 'variable_was_deleted'
os.getenv("EXAMPLE_VARIABLE", "variable_was_deleted")
# Output: 'variable_was_deleted'
