from __future__ import annotations

import base64
import dataclasses
import hashlib
import os
from typing import Literal
from urllib.parse import quote as url_quote

import aioaws.core
import aioaws.s3
import anyio
import httpx
from aioaws._types import S3ConfigProtocol

from fastenv.utilities import logger


class S3Config(aioaws.s3.S3Config):
    """Configure S3-compatible object storage.
    ---

    AWS S3 and Backblaze B2 are directly supported and tested.

    Buckets can be specified in "virtual hosted-style", like
    `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or
    `<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2.
    For AWS S3 only, the bucket can be also provided as just `<BUCKET_NAME>`.

    If credentials are not provided as arguments, this class will auto-detect
    configuration from the default AWS environment variables `AWS_ACCESS_KEY_ID`,
    `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN`, and the region from either
    `AWS_S3_REGION`, `AWS_REGION`, or `AWS_DEFAULT_REGION`, in that order.

    Boto3 detects credentials from several other locations, including credential files
    and instance metadata endpoints. These other locations are not currently supported.

    References:

    - https://www.backblaze.com/b2/docs/application_keys.html
    - https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
    - https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
    - https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
    - https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html
    """

    aws_secret_key: str = dataclasses.field(repr=False)
    aws_session_token: str = dataclasses.field(repr=False)

    def __init__(
        self,
        aws_access_key: str = "",
        aws_secret_key: str = "",
        aws_region: str = "",
        aws_s3_bucket: str = "",
        aws_session_token: str = "",
    ) -> None:
        aws_access_key = aws_access_key or os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        aws_session_token = aws_session_token or os.getenv("AWS_SESSION_TOKEN", "")
        if not aws_access_key or not aws_secret_key:
            raise RuntimeError("Required cloud credentials not present.")
        if not aws_s3_bucket:
            raise RuntimeError(
                "Required S3 bucket not present. Please provide a bucket domain, "
                "like `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or "
                "`<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2."
            )
        aws_region = (
            aws_region
            or os.getenv("AWS_S3_REGION", "")
            or os.getenv("AWS_REGION", "")
            or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.aws_region = aws_region
        self.aws_s3_bucket = aws_s3_bucket
        self.aws_session_token = aws_session_token


class S3Client(aioaws.s3.S3Client):
    """Instantiate a client to connect to S3-compatible object storage.
    ---

    AWS S3 and Backblaze B2 are directly supported and tested.

    This class requires both an HTTPX client and an `S3Config` instance.
    They will be automatically instantiated if not provided as arguments.
    Additional arguments (`**config_options`) will be used when automatically
    instantiating `S3Config`. In this scenario, minimally provide a bucket name
    with the `aws_s3_bucket` argument (`S3Client(aws_s3_bucket="bucket_name")`).

    Buckets can be specified in "virtual hosted-style", like
    `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or
    `<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2.
    For AWS S3 only, the bucket can be also provided as just `<BUCKET_NAME>`.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient = httpx.AsyncClient(),
        config: S3ConfigProtocol = None,
        **config_options: str,
    ) -> None:
        if not config:
            config = S3Config(**config_options)
        super().__init__(http_client, config)

    async def download(
        self,
        key: str = ".env",
        destination: os.PathLike[str] | str | None = None,
    ) -> anyio.Path | str:
        """Download a file from cloud object storage with HTTPX and aioaws.

        - `key`: path to the file within the bucket, without a leading `/`.
        - `destination`: whether to write object contents to a file or return as string.
          `destination=None` will return a string, which can be loaded into a `DotEnv`.
          `destination=".env"` will write to the destination and return a `Path` object.
        """
        try:
            download_url = self.signed_download_url(key)
            response = await self._aws_client.client.get(download_url)
            if response.status_code != 200:
                raise aioaws.core.RequestError(response)
            message = f"fastenv loaded {key} from {self._aws_client.host}"
            if destination:
                destination_path = anyio.Path(destination)
                await destination_path.write_text(response.text)
                logger.info(f"{message} and wrote the contents to {destination_path}")
                return destination_path
            logger.info(message)
            return response.text
        except Exception as e:
            logger.error(f"fastenv error: {e.__class__.__qualname__} {e}")
            raise

    async def upload(  # type: ignore[override]
        self,
        key: str = ".env",
        source: os.PathLike[str] | str | bytes = ".env",
        *,
        content_type: str = "text/plain",
        server_side_encryption: Literal["AES256"] | None = None,
    ) -> httpx.Response | None:
        """Upload a file to cloud object storage with HTTPX and aioaws.

        - `key`: path to the file within the bucket, without a leading `/`.
        - `source`: local file path or content to upload. Content will be converted
          to bytes prior to upload, if it is not provided as bytes directly. To use
          a `DotEnv` instance as a source, call `str()` on it, like
          `cloud_client.upload(source=str(dotenv))`.
        - `content_type`: media type to specify in the upload headers. See
          [Backblaze](https://www.backblaze.com/b2/docs/content-types.html)
          for a list of supported content types.
        - `server_side_encryption`: optional encryption algorithm to specify in the
          upload headers, which will be used to encrypt the file for object storage.
          AES256 encryption with Backblaze-managed keys ("SSE-B2") is supported. See
          [Backblaze](https://www.backblaze.com/b2/docs/server_side_encryption.html).
        """
        try:
            content, message = await self._encode_source(source)
            if "backblazeb2.com" in self._config.aws_s3_bucket:
                response: httpx.Response | None = await self.upload_to_backblaze_b2(
                    key,
                    content,
                    content_type=content_type,
                    server_side_encryption=server_side_encryption,
                )
            else:
                response = await super().upload(key, content, content_type=content_type)
            logger.info(
                f"{message} and wrote the contents to"
                f" {self._config.aws_s3_bucket}/{key}"
            )
            return response
        except Exception as e:
            logger.error(f"fastenv error: {e.__class__.__qualname__} {e}")
            raise

    async def _encode_source(
        self, source: os.PathLike[str] | str | bytes = ".env"
    ) -> tuple[bytes, str]:
        if isinstance(source, bytes):
            content = source
            message = "fastenv read the provided bytes"
        elif await (source_path := anyio.Path(source)).is_file():
            content = await source_path.read_bytes()
            message = f"fastenv loaded {source_path}"
        else:
            content = str(source).encode()
            message = "fastenv loaded the provided string"
        return content, message

    async def authorize_backblaze_b2_account(self) -> httpx.Response:
        """Get an authorization token and API URL from Backblaze B2.

        https://www.backblaze.com/b2/docs/b2_authorize_account.html
        """
        credentials = f"{self._config.aws_access_key}:{self._config.aws_secret_key}"
        base64_encoded_credentials = base64.b64encode(credentials.encode())
        headers = {"Authorization": f"Basic {base64_encoded_credentials.decode()}"}
        authorization_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
        return await self._aws_client.client.get(authorization_url, headers=headers)

    async def get_backblaze_b2_upload_url(
        self, authorization_response: httpx.Response
    ) -> httpx.Response:
        """Get an upload URL from Backblaze B2, using the authorization token
        and URL obtained from a call to `b2_authorize_account`.

        - https://www.backblaze.com/b2/docs/uploading.html
        - https://www.backblaze.com/b2/docs/b2_get_upload_url.html
        """
        authorization_response_json = authorization_response.json()
        authorization_token = authorization_response_json["authorizationToken"]
        bucket_id = authorization_response_json["allowed"]["bucketId"]
        api_url = authorization_response_json["apiUrl"]
        upload_request_url = f"{api_url}/b2api/v2/b2_get_upload_url"
        headers = {"Authorization": authorization_token}
        params = {"bucketId": bucket_id}
        return await self._aws_client.client.get(
            upload_request_url, headers=headers, params=params
        )

    async def upload_to_backblaze_b2(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str = "text/plain",
        server_side_encryption: Literal["AES256"] | None = None,
    ) -> httpx.Response:
        """Upload a file to Backblaze B2 object storage, using the authorization token
        and URL obtained from a call to `b2_get_upload_url`.

        - https://www.backblaze.com/b2/docs/uploading.html
        - https://www.backblaze.com/b2/docs/b2_upload_file.html
        """
        authorization_response = await self.authorize_backblaze_b2_account()
        upload_url_response = await self.get_backblaze_b2_upload_url(
            authorization_response=authorization_response
        )
        upload_url_response_json = upload_url_response.json()
        upload_url = upload_url_response_json["uploadUrl"]
        authorization_token = upload_url_response_json["authorizationToken"]
        content_sha1_digest = hashlib.sha1(content).hexdigest()
        headers = {
            "Authorization": authorization_token,
            "Content-Type": content_type,
            "X-Bz-Content-Sha1": content_sha1_digest,
            "X-Bz-File-Name": url_quote(key),
            "X-Bz-Info-Author": self._config.aws_access_key,
        }
        if server_side_encryption:
            headers["X-Bz-Server-Side-Encryption"] = server_side_encryption
        upload_response = await self._aws_client.client.post(
            upload_url, content=content, headers=headers
        )
        if upload_response.status_code not in {200, 204}:
            raise aioaws.core.RequestError(upload_response)
        return upload_response
