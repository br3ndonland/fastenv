"""fastenv

Unified environment variable and settings management for FastAPI and beyond.

https://github.com/br3ndonland/fastenv
"""
try:
    from .cloud.object_storage import ObjectStorageClient, ObjectStorageConfig
except ImportError:  # pragma: no cover
    pass
from .dotenv import DotEnv, dotenv_values, dump_dotenv, find_dotenv, load_dotenv

__all__ = (
    "DotEnv",
    "ObjectStorageClient",
    "ObjectStorageConfig",
    "dotenv_values",
    "dump_dotenv",
    "find_dotenv",
    "load_dotenv",
)
