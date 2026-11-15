#!/usr/bin/env python3
# example.py
import anyio
import fastenv


async def load_my_dotenv(filename: str = ".env") -> fastenv.DotEnv:
    dotenv = await fastenv.load_dotenv(filename)
    print(dotenv.source)
    print(dict(dotenv))
    return dotenv


async def load_my_dotenvs(*filenames: str) -> fastenv.DotEnv:
    dotenv = await fastenv.load_dotenv(*filenames)
    print(dotenv.source)
    print(dict(dotenv))
    return dotenv


async def load_and_dump_my_dotenvs(*filenames: str) -> fastenv.DotEnv:
    dotenv = await fastenv.load_dotenv(*filenames)
    await fastenv.dump_dotenv(dotenv, ".env.dump")
    return dotenv


if __name__ == "__main__":
    # anyio.run(load_my_dotenv)
    # anyio.run(load_my_dotenvs, ".env", ".env.override")
    anyio.run(load_and_dump_my_dotenvs, ".env", ".env.override")
