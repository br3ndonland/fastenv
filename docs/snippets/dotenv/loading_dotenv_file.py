#!/usr/bin/env python3
# example.py
import anyio
import fastenv


async def load_my_dotenv(filename: str = ".env") -> fastenv.DotEnv:
    dotenv = await fastenv.load_dotenv(filename)
    print(dotenv.source)
    print(dict(dotenv))
    return dotenv


if __name__ == "__main__":
    anyio.run(load_my_dotenv)
