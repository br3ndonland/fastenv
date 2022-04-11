from __future__ import annotations

import base64
import dataclasses
import datetime
import hashlib
import hmac
import json
import os
import urllib.parse
from typing import Literal

import anyio
import httpx

from fastenv.utilities import logger


@dataclasses.dataclass
class ObjectStorageConfig:
    """Configure S3-compatible object storage.
    ---

    AWS S3 and Backblaze B2 are directly supported and tested.

    Buckets can be specified in "virtual-hosted-style", like
    `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or
    `<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2.
    For AWS S3 only, the bucket can be also provided as just `<BUCKET_NAME>`.

    If credentials are not provided as arguments, this class will auto-detect
    configuration from the default AWS environment variables `AWS_ACCESS_KEY_ID`,
    `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN`, and the region from either
    `AWS_S3_REGION`, `AWS_REGION`, or `AWS_DEFAULT_REGION`, in that order.

    Boto3 detects credentials from several other locations, including credential files
    and instance metadata endpoints. These other locations are not currently supported.

    https://www.backblaze.com/b2/docs/application_keys.html
    https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
    https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
    https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
    https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html
    """

    access_key: str
    secret_key: str = dataclasses.field(repr=False)
    bucket_host: str
    bucket_name: str | None
    bucket_region: str
    session_token: str | None = dataclasses.field(default=None, repr=False)

    def __init__(
        self,
        access_key: str = None,
        secret_key: str = None,
        bucket_host: str = None,
        bucket_name: str = None,
        bucket_region: str = None,
        session_token: str = None,
    ) -> None:
        access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        if not access_key or not secret_key:
            raise AttributeError("Required cloud credentials not provided.")
        self.access_key = access_key
        self.secret_key = secret_key
        if not bucket_host and not bucket_name:
            raise AttributeError(
                "Required bucket info not provided. Please provide a bucket, "
                "like `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or "
                "`<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2."
            )
        elif bucket_host and not bucket_name:
            if (
                bucket_host.endswith(".amazonaws.com")
                or bucket_host.endswith(".backblazeb2.com")
            ) and bucket_name is None:
                self.bucket_name = bucket_host.split(".s3.")[0]
            else:
                self.bucket_name = None
        else:
            self.bucket_name = bucket_name
        bucket_region = (
            bucket_region
            or os.getenv("AWS_S3_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
        )
        if not bucket_region:
            raise AttributeError("Required bucket region not provided.")
        self.bucket_region = bucket_region
        self.bucket_host = (
            bucket_host or f"{bucket_name}.s3.{bucket_region}.amazonaws.com"
        )
        if self.bucket_name and self.bucket_name not in self.bucket_host:
            raise AttributeError(
                f"Bucket host {self.bucket_host} does not "
                f"include bucket name {self.bucket_name}."
            )
        if self.bucket_region not in self.bucket_host:
            raise AttributeError(
                f"Bucket host {self.bucket_host} does not "
                f"include bucket region {self.bucket_region}."
            )
        self.session_token = (
            session_token
            if session_token is not None
            else os.getenv("AWS_SESSION_TOKEN")
        )


class ObjectStorageClient:
    """Instantiate a client to connect to S3-compatible object storage.
    ---

    AWS S3 and Backblaze B2 are directly supported and tested.

    This class requires both an HTTPX client and an `ObjectStorageConfig` instance.
    They will be automatically instantiated if not provided as arguments.
    Any additional arguments will be used to instantiate `ObjectStorageConfig`.

    Buckets can be specified in "virtual-hosted-style", like
    `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or
    `<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2.
    For AWS S3 only, the bucket can be also provided as just `<BUCKET_NAME>`.

    https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html
    """

    __slots__ = "_client", "_config"

    def __init__(
        self,
        client: httpx.AsyncClient = None,
        config: ObjectStorageConfig = None,
        **config_options: str,
    ) -> None:
        self._client = client or httpx.AsyncClient()
        self._config = config or ObjectStorageConfig(**config_options)

    async def download(
        self,
        bucket_path: os.PathLike[str] | str = ".env",
        destination: os.PathLike[str] | str | None = None,
    ) -> anyio.Path | str:
        """Download a file from cloud object storage.

        `bucket_path`: path to the source file within the bucket.

        `destination`: local file path to which to write object contents.
        `destination=None` will return a string, which can be loaded into a `DotEnv`.
        `destination=".env"` will write to the destination and return a `Path` object.
        """
        try:
            download_url = self.generate_presigned_url("GET", bucket_path, expires=30)
            response = await self._client.get(download_url)
            response.raise_for_status()
            message = f"fastenv loaded {bucket_path} from {self._config.bucket_host}"
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

    def generate_presigned_url(
        self,
        method: Literal["DELETE", "GET", "HEAD", "POST", "PUT"],
        bucket_path: os.PathLike[str] | str,
        *,
        expires: int = 3600,
        service: str = "s3",
    ) -> httpx.URL:
        """Generate a presigned URL for downloads from S3-compatible object storage.

        Requests to S3-compatible object storage can be authenticated either with
        request headers or query parameters. Presigned URLs use query parameters.
        The advantage to using query parameters is that URLs can be used on their own.

        `method`: HTTP method to use. Presigned URLs are typically used with GET or PUT.
        For POST support, see `generate_presigned_post`.

        `bucket_path`: path to the source file within the bucket.
        AWS calls bucket paths "keys," but the argument name here is `bucket_path`
        to avoid confusion with other "keys" like AWS access keys.

        `expires`: seconds until the URL expires. The default and maximum
        expiration times are the same as the AWS CLI and Boto3.

        `service`: cloud service for which to generate the presigned URL.

        https://awscli.amazonaws.com/v2/documentation/api/latest/reference/s3/presign.html
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
        https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html
        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
        https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html
        """
        if expires < 1 or expires > 604800:
            raise ValueError("Expiration time must be between one second and one week.")
        key = key if (key := str(bucket_path)).startswith("/") else f"/{key}"
        params = self._set_presigned_url_query_params(
            method, key, expires=expires, service=service
        )
        return httpx.URL(
            scheme="https", host=self._config.bucket_host, path=key, params=params
        )

    def _set_presigned_url_query_params(
        self,
        method: Literal["DELETE", "GET", "HEAD", "POST", "PUT"],
        key: str,
        *,
        expires: int,
        service: str = "s3",
        payload_hash: str = "UNSIGNED-PAYLOAD",
    ) -> httpx.QueryParams:
        """Set query parameters for a presigned URL.

        Setting presigned URL query parameters is a four-step process
        that requires an implementation of AWS Signature Version 4:
        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html

        1. Create canonical request
        2. Create string to sign
        3. Calculate signature
        4. Add signature to request

        This function performs the four steps and returns an instance of
        `httpx.QueryParams` that complies with AWS Signature Version 4.

        As of HTTPX 0.18, instances of `httpx.QueryParams` are immutable.
        When multiple instances of query params are supplied in the same
        request, HTTPX will merge them into a new instance.
        https://github.com/encode/httpx/discussions/1599
        https://github.com/encode/httpx/releases/tag/0.18.0
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        x_amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        credential_scope = (
            f"{date_stamp}/{self._config.bucket_region}/{service}/aws4_request"
        )
        x_amz_credential = f"{self._config.access_key}/{credential_scope}"
        params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": x_amz_credential,
            "X-Amz-Date": x_amz_date,
            "X-Amz-Expires": str(expires),
        }
        if self._config.session_token:
            params["X-Amz-Security-Token"] = self._config.session_token
        params["X-Amz-SignedHeaders"] = "host"
        headers = {"host": self._config.bucket_host}
        # 1. create canonical request
        canonical_request = self._create_canonical_request(
            method=method,
            key=key,
            params=params,
            headers=headers,
            payload_hash=payload_hash,
        )
        # 2. create string to sign
        string_to_sign = self._create_string_to_sign(
            x_amz_date=x_amz_date,
            credential_scope=credential_scope,
            canonical_request=canonical_request,
        )
        # 3. calculate signature
        signing_key = self._derive_signing_key(date_stamp)
        signature = self._calculate_signature(signing_key, string_to_sign)
        # 4. add signature to request
        params["X-Amz-Signature"] = signature
        return httpx.QueryParams(params)

    @staticmethod
    def _create_canonical_request(
        method: Literal["DELETE", "GET", "HEAD", "POST", "PUT"],
        key: str,
        params: dict[str, str],
        headers: dict[str, str],
        payload_hash: str,
    ) -> str:
        """Create a canonical request for AWS Signature Version 4.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
        https://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html

        There should be two line breaks after the `canonical_headers`.
        """
        canonical_uri = urllib.parse.quote(key if key.startswith("/") else f"/{key}")
        canonical_query_params = httpx.QueryParams(params)
        canonical_query_string = str(canonical_query_params)
        header_keys = sorted(headers)
        canonical_headers = "".join(f"{key}:{headers[key]}\n" for key in header_keys)
        signed_headers = ";".join(header_keys)
        canonical_request_parts = (
            method,
            canonical_uri,
            canonical_query_string,
            canonical_headers,
            signed_headers,
            payload_hash,
        )
        return "\n".join(canonical_request_parts)

    @staticmethod
    def _create_string_to_sign(
        x_amz_date: str,
        credential_scope: str,
        canonical_request: str,
    ) -> str:
        """Create a string to sign for AWS Signature Version 4.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
        https://docs.aws.amazon.com/general/latest/gr/sigv4-create-string-to-sign.html
        """
        canonical_request_bytes = canonical_request.encode()
        request_digest = hashlib.sha256(canonical_request_bytes).hexdigest()
        string_to_sign_parts = (
            "AWS4-HMAC-SHA256",
            x_amz_date,
            credential_scope,
            request_digest,
        )
        return "\n".join(string_to_sign_parts)

    @staticmethod
    def _new_hmac_digest(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode(), hashlib.sha256).digest()

    def _derive_signing_key(self, date_stamp: str, service: str = "s3") -> bytes:
        """Derive a signing key used to calculate AWS Signature Version 4.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
        https://docs.aws.amazon.com/general/latest/gr/sigv4-calculate-signature.html
        https://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html
        """
        secret_key = f"AWS4{self._config.secret_key}".encode()
        date_key = self._new_hmac_digest(secret_key, date_stamp)
        date_region_key = self._new_hmac_digest(date_key, self._config.bucket_region)
        date_region_service_key = self._new_hmac_digest(date_region_key, service)
        return self._new_hmac_digest(date_region_service_key, "aws4_request")

    @staticmethod
    def _calculate_signature(signing_key: bytes, string_to_sign: str) -> str:
        """Calculate a signature for AWS Signature Version 4.

        https://docs.aws.amazon.com/general/latest/gr/sigv4-calculate-signature.html
        """
        signing_message = string_to_sign.encode()
        return hmac.new(signing_key, signing_message, hashlib.sha256).hexdigest()

    @staticmethod
    async def _encode_source(
        source: os.PathLike[str] | str | bytes = ".env",
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

    async def upload(
        self,
        bucket_path: os.PathLike[str] | str = ".env",
        source: os.PathLike[str] | str | bytes = ".env",
        *,
        content_type: str = "text/plain",
        server_side_encryption: Literal["AES256", None] = None,
    ) -> httpx.Response | None:
        """Upload a file to cloud object storage.

        `bucket_path`: destination path for the uploaded file within the bucket.

        `source`: local file path or content to upload. Content will be converted
        to bytes prior to upload, if it is not provided as bytes directly. To use
        a `DotEnv` instance as a source, call `str()` on it, like
        `object_storage_client.upload(source=str(dotenv))`.

        `content_type`: content type to specify for the uploaded object.
        See Backblaze for a list of supported content types.
        https://www.backblaze.com/b2/docs/content-types.html

        `server_side_encryption`: optional encryption algorithm to specify,
        which the object storage platform will use to encrypt the file for storage.
        This method supports AES256 encryption with managed keys,
        referred to as "SSE-B2" on Backblaze or "SSE-S3" on AWS S3.
        https://www.backblaze.com/b2/docs/server_side_encryption.html
        https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html
        """
        try:
            content, message = await self._encode_source(source)
            if self._config.bucket_host.endswith(".backblazeb2.com"):
                response = await self.upload_to_backblaze_b2(
                    bucket_path,
                    content,
                    content_type=content_type,
                    server_side_encryption=server_side_encryption,
                )
            else:
                url, data = self.generate_presigned_post(
                    bucket_path,
                    content_length=len(content),
                    content_type=content_type,
                    expires=30,
                    server_side_encryption=server_side_encryption,
                )
                response = await self._client.post(
                    url, data=data, files={"file": content}
                )
            response.raise_for_status()
            logger.info(
                f"{message} and wrote the contents to"
                f" {self._config.bucket_host}/{bucket_path}"
            )
            return response
        except Exception as e:
            logger.error(f"fastenv error: {e.__class__.__qualname__} {e}")
            raise

    def generate_presigned_post(
        self,
        bucket_path: os.PathLike[str] | str,
        *,
        expires: int = 3600,
        service: str = "s3",
        content_length: int | None = None,
        content_type: str = "text/plain",
        server_side_encryption: Literal["AES256", None] = None,
        specify_content_disposition: bool = True,
        additional_policy_conditions: list | None = None,
        additional_form_data: dict[str, str] | None = None,
    ) -> tuple[httpx.URL, dict[str, str]]:
        """Generate the URL and form fields for a POST to S3-compatible object storage.

        Instead of using query parameters like presigned URLs, uploads to AWS S3 with
        `POST` can provide authentication information in form fields. An advantage of
        this approach is that it can also be used for browser-based uploads.
        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-authentication-HTTPPOST.html

        `bucket_path`: destination path for the uploaded file within the bucket.
        AWS calls bucket paths "keys," but the argument name here is `bucket_path`
        to avoid confusion with other "keys" like AWS access keys.

        `expires`: seconds until the presigned `POST` expires.
        The default expiration time is the same as for Boto3.

        `service`: cloud service for which to generate the presigned URL.

        `content_length`: length of the message body (the object to upload) in bytes.

        `content_type`: content type to specify for the uploaded object.
        See Backblaze for a list of supported content types.
        https://www.backblaze.com/b2/docs/content-types.html

        `server_side_encryption`: optional encryption algorithm to specify,
        which the object storage platform will use to encrypt the file for storage.
        This method supports AES256 encryption with managed keys,
        referred to as "SSE-B2" on Backblaze or "SSE-S3" on AWS S3.
        https://www.backblaze.com/b2/docs/server_side_encryption.html
        https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html

        `specify_content_disposition`: the HTTP header `Content-Disposition` indicates
        whether the content is expected to be displayed inline (in the browser) or
        downloaded to a file (referred to as an "attachment"). Dotenv files are
        typically downloaded instead of being displayed in the browser, so by default,
        fastenv will add `Content-Disposition: attachment; filename="{filename}"`.
        https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Disposition

        `additional_policy_conditions`: additional POST policy conditions to specify.
        See https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html.

        `additional_form_data`: additional form data keys and values to return.

        The return type is similar to Boto3's `generate_presigned_post` method,
        but returns a two-tuple instead of a dict.
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
        """
        key = key.lstrip("/") if (key := str(bucket_path)).startswith("/") else key
        url = httpx.URL(scheme="https", host=self._config.bucket_host, path="/")
        form_data = self._set_presigned_post_form_data(
            key,
            content_length=content_length,
            content_type=content_type,
            expires=expires,
            service=service,
            server_side_encryption=server_side_encryption,
            specify_content_disposition=specify_content_disposition,
            additional_policy_conditions=additional_policy_conditions,
            additional_form_data=additional_form_data,
        )
        return url, form_data

    def _set_presigned_post_form_data(
        self,
        key: str,
        *,
        expires: int = 3600,
        service: str = "s3",
        content_length: int | None = None,
        content_type: str = "text/plain",
        server_side_encryption: Literal["AES256", None] = None,
        specify_content_disposition: bool = True,
        additional_policy_conditions: list | None = None,
        additional_form_data: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Set form data for a presigned POST.

        Setting presigned POST form data is a four-step process
        that requires an implementation of AWS Signature Version 4:
        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-authentication-HTTPPOST.html
        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html
        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html

        1. Create POST policy (instead of canonical request like query string auth)
        2. Create string to sign by UTF-8-encoding the policy and converting to Base64
        3. Calculate signature
        4. Add signature to form data

        This function performs the four steps and returns a `dict` suitable for
        submission as form data in the `data` argument of an HTTPX POST request.

        The expiration time format for a POST policy is different from `X-Amz-Date`,
        though AWS calls both ISO 8601. Python datetime objects do not automatically
        provide milliseconds, but the `timespec` argument to `isoformat` can be used.

        Policy condition and form field keys are case-insensitive.
        For example, either `x-amz-signature` or `X-Amz-Signature` are valid keys.
        All policy condition keys will be normalized to lowercase.
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        x_amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        expiration_time = now + datetime.timedelta(seconds=expires)
        expiration_time_isoformat = expiration_time.isoformat(timespec="milliseconds")
        expiration = expiration_time_isoformat.replace("+00:00", "Z")
        credential_scope = (
            f"{date_stamp}/{self._config.bucket_region}/{service}/aws4_request"
        )
        x_amz_credential = f"{self._config.access_key}/{credential_scope}"
        required_form_data = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": x_amz_credential,
            "X-Amz-Date": x_amz_date,
        }
        if self._config.session_token:
            required_form_data["X-Amz-Security-Token"] = self._config.session_token
        # 1. create POST policy
        required_policy_conditions = [
            {key: value} for key, value in required_form_data.items()
        ]
        policy = self._create_presigned_post_policy(
            expiration,
            required_policy_conditions,
            key,
            content_length=content_length,
            content_type=content_type,
            server_side_encryption=server_side_encryption,
            specify_content_disposition=specify_content_disposition,
            additional_policy_conditions=additional_policy_conditions,
        )
        # 2. create string to sign
        string_to_sign = base64.b64encode(json.dumps(policy).encode()).decode()
        # 3. calculate signature
        signing_key = self._derive_signing_key(date_stamp)
        signature = self._calculate_signature(signing_key, string_to_sign)
        # 4. add signature to form data
        form_data = self._prepare_presigned_post_form_data(policy, additional_form_data)
        return {"policy": string_to_sign, **form_data, "x-amz-signature": signature}

    def _create_presigned_post_policy(
        self,
        expiration: str,
        required_policy_conditions: list[dict[str, str]],
        key: str,
        *,
        content_length: int | None,
        content_type: str | None,
        server_side_encryption: Literal["AES256", None],
        specify_content_disposition: bool,
        additional_policy_conditions: list | None,
    ) -> dict[Literal["expiration", "conditions"], str | dict[str, str] | list]:
        """Create an upload policy for a presigned POST.

        Setting presigned POST form data is a four-step process
        that requires an implementation of AWS Signature Version 4:

        1. Create POST policy (instead of canonical request like query string auth)
        2. Create string to sign by UTF-8-encoding the policy and converting to Base64
        3. Calculate signature
        4. Add signature to form data

        This function performs step 1 and returns a POST policy.

        The expiration time format for a POST policy is different from `X-Amz-Date`,
        though AWS calls both ISO 8601. Python datetime objects do not automatically
        provide milliseconds, but the `timespec` argument to `isoformat` can be used.

        Policy condition and form field keys are case-insensitive.
        For example, either `x-amz-signature` or `X-Amz-Signature` are valid keys.
        This function will normalize all policy condition keys to lowercase.
        """
        policy_conditions: list = required_policy_conditions
        if self._config.bucket_name:
            policy_conditions.append({"bucket": self._config.bucket_name})
        if key and "${filename}" in key:
            starts_with_key = key.split(sep="${filename}")[0]
            policy_conditions.append(["starts-with", "$key", starts_with_key])
        elif key:
            policy_conditions.append({"key": key})
        if (
            specify_content_disposition
            and (filename := key.split(sep="/")[-1])
            and filename != "${filename}"
        ):
            policy_conditions.append(
                {"content-disposition": f'attachment; filename="{filename}"'}
            )
        if content_length:
            policy_conditions.append(
                ["content-length-range", content_length, content_length]
            )
        if content_type:
            policy_conditions.append({"content-type": content_type})
        if self._config.session_token:
            policy_conditions.append(
                {"x-amz-security-token": self._config.session_token}
            )
        if server_side_encryption:
            policy_conditions.append(
                {"x-amz-server-side-encryption": server_side_encryption}
            )
        if additional_policy_conditions:
            policy_conditions += additional_policy_conditions
        for i, policy_condition in enumerate(policy_conditions):
            if isinstance(policy_condition, dict):
                policy_conditions[i] = {
                    key.casefold(): value for key, value in policy_condition.items()
                }
            elif isinstance(policy_condition, list):
                policy_condition[0] = str(policy_condition[0]).casefold()
                policy_conditions[i] = policy_condition
        deduplicated_policy_conditions = [
            policy_condition
            for i, policy_condition in enumerate(policy_conditions)
            if policy_condition not in policy_conditions[:i]
        ]
        return {"expiration": expiration, "conditions": deduplicated_policy_conditions}

    @staticmethod
    def _prepare_presigned_post_form_data(
        policy: dict[Literal["expiration", "conditions"], str | dict[str, str] | list],
        additional_form_data: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Assemble form data for a presigned POST.

        Setting presigned POST form data is a four-step process
        that requires an implementation of AWS Signature Version 4:

        1. Create POST policy (instead of canonical request like query string auth)
        2. Create string to sign by UTF-8-encoding the policy and converting to Base64
        3. Calculate signature
        4. Add signature to form data

        This function accepts a POST policy (step 1) and returns form data for step 4.
        The upload policy and signature are then added to the form data.

        "key" is a required form data field, though the docs are not clear on this.
        "key" is not always included in policies directly. For example, an upload
        policy may need to allow the user to supply a filename. In this case, the
        filename is not known ahead of time, so an exact "key" condition cannot be
        set. Other forms of condition matching such as "starts-with" can be used,
        and the form data should supply a template field like `${filename}`.
        """
        supported_form_data_keys = {
            "acl",
            "cache-control",
            "content-disposition",
            "content-encoding",
            "content-type",
            "expires",
            "key",
            "redirect",
            "success_action_redirect",
            "success_action_status",
            "x-amz-algorithm",
            "x-amz-credential",
            "x-amz-date",
            "x-amz-security-token",
            "x-amz-server-side-encryption",
        }
        form_data_from_policy = {
            casefolded_key: value
            for policy_condition in policy["conditions"]
            if isinstance(policy_condition, dict)
            for key, value in policy_condition.items()
            if (casefolded_key := str(key).casefold()) in supported_form_data_keys
            or casefolded_key.startswith("x-amz-meta-")
        }
        if additional_form_data:
            additional_form_data = {
                str(key).casefold(): value
                for key, value in additional_form_data.items()
            }
            form_data_to_return = {**form_data_from_policy, **additional_form_data}
        else:
            form_data_to_return = form_data_from_policy
        for form_data_key in form_data_to_return:
            if (
                form_data_key not in supported_form_data_keys
                and not form_data_key.startswith("x-amz-meta-")
            ):
                raise KeyError(f"Unsupported form data key: {form_data_key}")
        form_data_key_item = form_data_to_return.get("key")
        if form_data_key_item and isinstance(form_data_key_item, str):
            return form_data_to_return
        elif form_data_key_item:
            raise KeyError(
                f"Incorrect data type {type(form_data_key_item)} "
                f"in form data: {{'key': {form_data_key_item}}}."
            )
        else:
            if form_data_key_items := [
                str(policy_condition[2]) + "${filename}"
                for policy_condition in policy["conditions"]
                if isinstance(policy_condition, list)
                and policy_condition[0] == "starts-with"
                and policy_condition[1] == "$key"
                and str(policy_condition[2]).endswith("/")
            ]:
                form_data_to_return["key"] = str(form_data_key_items[0])
            else:
                raise KeyError("Missing required form data key: key")
        return form_data_to_return

    async def authorize_backblaze_b2_account(self) -> httpx.Response:
        """Get an authorization token and API URL from Backblaze B2.

        https://www.backblaze.com/b2/docs/b2_authorize_account.html
        """
        credentials = f"{self._config.access_key}:{self._config.secret_key}"
        base64_encoded_credentials = base64.b64encode(credentials.encode())
        headers = {"Authorization": f"Basic {base64_encoded_credentials.decode()}"}
        authorization_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
        return await self._client.get(authorization_url, headers=headers)

    async def get_backblaze_b2_upload_url(
        self, authorization_response: httpx.Response
    ) -> httpx.Response:
        """Get an upload URL from Backblaze B2, using the authorization token
        and URL obtained from a call to `b2_authorize_account`.

        https://www.backblaze.com/b2/docs/uploading.html
        https://www.backblaze.com/b2/docs/b2_get_upload_url.html
        """
        authorization_response_json = authorization_response.json()
        authorization_token = authorization_response_json["authorizationToken"]
        bucket_id = authorization_response_json["allowed"]["bucketId"]
        api_url = authorization_response_json["apiUrl"]
        upload_request_url = f"{api_url}/b2api/v2/b2_get_upload_url"
        headers = {"Authorization": authorization_token}
        params = {"bucketId": bucket_id}
        return await self._client.get(
            upload_request_url, headers=headers, params=params
        )

    async def upload_to_backblaze_b2(
        self,
        bucket_path: os.PathLike[str] | str,
        content: bytes,
        *,
        content_type: str = "text/plain",
        server_side_encryption: Literal["AES256", None] = None,
    ) -> httpx.Response:
        """Upload a file to Backblaze B2 object storage, using the authorization token
        and URL obtained from a call to `b2_get_upload_url`.

        https://www.backblaze.com/b2/docs/uploading.html
        https://www.backblaze.com/b2/docs/b2_upload_file.html
        """
        authorization_response = await self.authorize_backblaze_b2_account()
        upload_url_response = await self.get_backblaze_b2_upload_url(
            authorization_response=authorization_response
        )
        upload_url_response_json = upload_url_response.json()
        upload_url = upload_url_response_json["uploadUrl"]
        authorization_token = upload_url_response_json["authorizationToken"]
        x_bz_content_sha1 = hashlib.sha1(content).hexdigest()
        x_bz_file_name = urllib.parse.quote(str(bucket_path))
        headers = {
            "Authorization": authorization_token,
            "Content-Type": content_type,
            "X-Bz-Content-Sha1": x_bz_content_sha1,
            "X-Bz-File-Name": x_bz_file_name,
            "X-Bz-Info-Author": self._config.access_key,
        }
        if server_side_encryption:
            headers["X-Bz-Server-Side-Encryption"] = server_side_encryption
        return await self._client.post(upload_url, content=content, headers=headers)
