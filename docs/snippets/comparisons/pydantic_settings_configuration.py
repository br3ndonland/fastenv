import os

from fastenv import BaseSettings

os.environ["BOOLEAN_SETTING"] = "false"
os.environ["INTEGER_SETTING"] = "123"
os.environ["STRING_SETTING"] = "example_value"


class SimpleSettings(BaseSettings):
    boolean_setting: bool = True
    integer_setting: int = 000
    string_setting: str = "default_value"


print(SimpleSettings().model_dump())
# Output: {'boolean_setting': False, 'integer_setting': 123, 'string_setting': 'example_value'}
