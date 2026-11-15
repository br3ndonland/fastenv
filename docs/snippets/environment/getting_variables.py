import fastenv

dotenv = fastenv.DotEnv("KEY1=value1")
dotenv("KEY1")
# Output: 'value1'
dotenv("NOT_SET")
dotenv.getenv("NOT_SET", "default_value")
# Output: 'default_value'
dotenv("KEY1", "NOT_SET NOT_SET_EITHER")
# Output: {'KEY1': 'value1', 'NOT_SET': None, 'NOT_SET_EITHER': None}
