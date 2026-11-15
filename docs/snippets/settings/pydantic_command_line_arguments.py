# pyright: reportAny=false
import argparse

from fastenv import BaseSettings


class Settings(BaseSettings):
    port: int = 8000


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=argparse.SUPPRESS)
overrides = vars(parser.parse_args())
settings = Settings(**overrides)
