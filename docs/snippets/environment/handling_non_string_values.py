# pyright: reportArgumentType=false
import fastenv

dotenv = fastenv.DotEnv(incorrect_type=[1, 2, 3])
dict(dotenv)
# Output: {'INCORRECT_TYPE': '[1, 2, 3]'}
