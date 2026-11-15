#!/usr/bin/env python3
# example.py
from __future__ import annotations

import anyio
import fastenv
import httpx2


async def upload_my_dotenv(
    bucket_host: str,
    bucket_region: str,
    bucket_path: str = "uploads/fastenv-docs/.env",
    source: anyio.Path | str = ".env",
) -> httpx2.Response | None:
    config = fastenv.ObjectStorageConfig(  # (1)
        bucket_host=bucket_host,
        bucket_region=bucket_region,
    )
    client = fastenv.ObjectStorageClient(config=config)  # (2)
    return await client.upload(bucket_path, source)  # (3)


if __name__ == "__main__":
    bucket_host = "<BUCKET_NAME>.s3.<REGION>.backblazeb2.com"
    bucket_region = "<REGION>"
    anyio.run(upload_my_dotenv, bucket_host, bucket_region)
