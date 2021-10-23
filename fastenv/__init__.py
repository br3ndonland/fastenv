"""fastenv

Unified environment variable and settings management for FastAPI and beyond.

https://github.com/br3ndonland/fastenv
"""
try:
    from .cloud import S3Client, S3Config
except ImportError:  # pragma: no cover
    pass
from .dotenv import DotEnv, dotenv_values, dump_dotenv, find_dotenv, load_dotenv

__all__ = (
    "S3Client",
    "S3Config",
    "DotEnv",
    "dotenv_values",
    "dump_dotenv",
    "find_dotenv",
    "load_dotenv",
)
