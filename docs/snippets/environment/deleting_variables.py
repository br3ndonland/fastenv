import fastenv

dotenv = fastenv.DotEnv()
dotenv("KEY1=value1", "KEY2=value2 KEY3=value3", key4="value4")
# Output: {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3', 'KEY4': 'value4'}
del dotenv["KEY4"]
dotenv.delenv("KEY1", "KEY2", "KEY3")
len(dotenv)
# Output: 0
