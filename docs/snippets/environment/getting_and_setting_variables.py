import fastenv

dotenv = fastenv.DotEnv("KEY1=value1")
dotenv("KEY1", "KEY2=value2 KEY3=value3", key4="value4")
# Output: {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4'}
