#!/usr/bin/env python3
# example.py
from __future__ import annotations

import anyio
import fastenv


async def download_my_dotenvs(
    bucket_host: str,
    bucket_region: str,
    bucket_path_to_common_env: str = ".env.common",
    bucket_path_to_custom_env: str = ".env.custom",
) -> fastenv.DotEnv:
    config = fastenv.ObjectStorageConfig(
        bucket_host=bucket_host,
        bucket_region=bucket_region,
    )
    client = fastenv.ObjectStorageClient(config=config)
    env_common = await client.download(bucket_path_to_common_env)
    env_custom = await client.download(bucket_path_to_custom_env)
    return await fastenv.load_dotenv(env_common, env_custom)


if __name__ == "__main__":
    bucket_host = "<BUCKET_NAME>.s3.<REGION>.backblazeb2.com"
    bucket_region = "<REGION>"
    anyio.run(download_my_dotenvs, bucket_host, bucket_region)
