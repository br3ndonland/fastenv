import fastenv

dotenv = fastenv.DotEnv()
dotenv("KEY1=value1", "KEY2=value2 KEY3=value3", key4="value4")
# Output: {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4'}
dotenv.setenv(key5="value5")
dict(dotenv)
# Output: {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4', 'KEY5': 'value5'}
