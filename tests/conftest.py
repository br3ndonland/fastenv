from __future__ import annotations

import datetime
import os
import secrets
import urllib.parse
from typing import TYPE_CHECKING, NamedTuple

import anyio
import pytest

import fastenv.cloud.object_storage

if TYPE_CHECKING:
    from typing import Any

    from fastenv.types import UploadPolicy


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Specify the back-end for pytest to use when running async functions
    with [AnyIO](https://anyio.readthedocs.io/en/stable/testing.html).
    """
    return "asyncio"


class CloudParams(NamedTuple):
    access_key_variable: str
    secret_key_variable: str
    session_token_variable: str
    bucket_host_variable: str
    bucket_region_variable: str


_cloud_params_aws_session = CloudParams(
    access_key_variable="AWS_IAM_ACCESS_KEY_SESSION",
    secret_key_variable="AWS_IAM_SECRET_KEY_SESSION",
    session_token_variable="AWS_IAM_SESSION_TOKEN",
    bucket_host_variable="AWS_S3_BUCKET_HOST",
    bucket_region_variable="AWS_S3_BUCKET_REGION",
)
_cloud_params_aws_static = CloudParams(
    access_key_variable="AWS_IAM_ACCESS_KEY_FASTENV",
    secret_key_variable="AWS_IAM_SECRET_KEY_FASTENV",
    session_token_variable="",
    bucket_host_variable="AWS_S3_BUCKET_HOST",
    bucket_region_variable="AWS_S3_BUCKET_REGION",
)
_cloud_params_backblaze_static = CloudParams(
    access_key_variable="BACKBLAZE_B2_ACCESS_KEY_FASTENV",
    secret_key_variable="BACKBLAZE_B2_SECRET_KEY_FASTENV",
    session_token_variable="",
    bucket_host_variable="BACKBLAZE_B2_BUCKET_HOST",
    bucket_region_variable="BACKBLAZE_B2_BUCKET_REGION",
)
_cloud_params_cloudflare_static = CloudParams(
    access_key_variable="CLOUDFLARE_R2_ACCESS_KEY_FASTENV",
    secret_key_variable="CLOUDFLARE_R2_SECRET_KEY_FASTENV",
    session_token_variable="",
    bucket_host_variable="CLOUDFLARE_R2_BUCKET_HOST",
    bucket_region_variable="auto",
)


@pytest.fixture(
    params=(
        _cloud_params_aws_session,
        _cloud_params_aws_static,
        _cloud_params_backblaze_static,
        _cloud_params_cloudflare_static,
    ),
    scope="session",
)
def object_storage_config(
    request: pytest.FixtureRequest,
) -> fastenv.cloud.object_storage.ObjectStorageConfig:
    """Provide cloud configurations for testing.

    This fixture will retrieve cloud credentials from environment variables, then
    use the credentials to return `fastenv.cloud.object_storage.ObjectStorageConfig`
    instances for testing.

    This is a parametrized fixture. When the fixture is used in a test, the test
    will be automatically parametrized, running once for each fixture parameter.
    https://docs.pytest.org/en/latest/how-to/fixtures.html
    """
    request_param: CloudParams = getattr(request, "param")
    access_key = os.getenv(request_param.access_key_variable)
    secret_key = os.getenv(request_param.secret_key_variable)
    session_token = (
        os.getenv(request_param.session_token_variable)
        if request_param.session_token_variable
        else request_param.session_token_variable
    )
    bucket_host = os.getenv(request_param.bucket_host_variable)
    bucket_region = os.getenv(request_param.bucket_region_variable)
    if not access_key or not secret_key or session_token is None:  # pragma: no cover
        pytest.skip("Required cloud credentials not present.")
    return fastenv.cloud.object_storage.ObjectStorageConfig(
        access_key=access_key,
        secret_key=secret_key,
        bucket_host=bucket_host,
        bucket_region=bucket_region,
        session_token=session_token,
    )


@pytest.fixture(scope="session")
def object_storage_config_backblaze_static() -> (
    fastenv.cloud.object_storage.ObjectStorageConfig
):
    """Provide a single cloud configuration instance for testing.

    Rather than parametrizing all the cloud configurations, this fixture sets up
    a single `fastenv.cloud.object_storage.ObjectStorageConfig` instance for testing.
    """
    access_key = os.getenv(_cloud_params_backblaze_static.access_key_variable)
    secret_key = os.getenv(_cloud_params_backblaze_static.secret_key_variable)
    if not access_key or not secret_key:  # pragma: no cover
        pytest.skip("Required cloud credentials not present.")
    bucket_host = os.getenv(_cloud_params_backblaze_static.bucket_host_variable)
    bucket_host = os.getenv(_cloud_params_backblaze_static.bucket_host_variable)
    bucket_region = os.getenv(_cloud_params_backblaze_static.bucket_region_variable)
    return fastenv.cloud.object_storage.ObjectStorageConfig(
        access_key=access_key,
        secret_key=secret_key,
        bucket_host=bucket_host,
        bucket_region=bucket_region,
    )


@pytest.fixture(scope="session")
def object_storage_config_incorrect() -> (
    fastenv.cloud.object_storage.ObjectStorageConfig
):
    """Provide a single cloud configuration instance for testing.

    Rather than parametrizing all the cloud configurations, this fixture sets up
    a single `fastenv.cloud.object_storage.ObjectStorageConfig` instance for testing.

    This particular configuration is provided for testing authorization errors.
    """
    bucket_host = os.getenv("AWS_S3_BUCKET_HOST")
    bucket_region = os.getenv("AWS_S3_REGION", "us-east-2")
    return fastenv.cloud.object_storage.ObjectStorageConfig(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE",
        bucket_host=bucket_host,
        bucket_region=bucket_region,
    )


@pytest.fixture(params=(False, True))
def object_storage_config_for_presigned_url_example(
    request: pytest.FixtureRequest,
) -> fastenv.cloud.object_storage.ObjectStorageConfig:
    """Provide a single cloud configuration instance with data from the AWS docs.

    https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html

    The virtual-hosted-style URL in this example lacks a region. The docs mix
    path-style URLs (`s3.amazonaws.com/examplebucket`), virtual-hosted-style URLs
    without regions (`examplebucket.s3.amazonaws.com`), and virtual-hosted-style
    URLs with regions (`examplebucket.s3.us-east-1.amazonaws.com`).
    """
    use_session_token: bool = getattr(request, "param")
    if use_session_token is True:
        # docs only provide the quoted session token
        quoted_session_token = (
            "IQoJb3JpZ2luX2VjEMv%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJGME"
            "QCIBSUbVdj9YGs2g0HkHsOHFdkwOozjARSKHL987NhhOC8AiBPepRU1obMvIbGU0T%2BWp"
            "hFPgK%2Fqpxaf5Snvm5M57XFkCqlAgjz%2F%2F%2F%2F%2F%2F%2F%2F%2F%2F8BEAAaDD"
            "Q3MjM4NTU0NDY2MCIM83pULBe5%2F%2BNm1GZBKvkBVslSaJVgwSef7SsoZCJlfJ56weYl"
            "3QCwEGr2F4BmCZZyFpmWEYzWnhNK1AnHMj5nkfKlKBx30XAT5PZGVrmq4Vkn9ewlXQy1Iu"
            "3QJRi9Tdod8Ef9%2FyajTaUGh76%2BF5u5a4O115jwultOQiKomVwO318CO4l8lv%2F3Hh"
            "MOkpdanMXn%2B4PY8lvM8RgnzSu90jOUpGXEOAo%2F6G8OqlMim3%2BZmaQmasn4VYRvES"
            "Ed7O72QGZ3%2BvDnDVnss0lSYjlv8PP7IujnvhZRnj0WoeOyMe1lL0wTG%2Fa9usH5hE52"
            "w%2FYUJccOn0OaZuyROuVsRV4Q70sbWQhUvYUt%2B0tUMKzm8vsFOp4BaNZFqobbjtb36Y"
            "92v%2Bx5kY6i0s8QE886jJtUWMP5ldMziClGx3p0mN5dzsYlM3GyiJ%2FO1mWkPQDwg3mt"
            "SpOA9oeeuAMPTA7qMqy9RNuTKBDSx9EW27wvPzBum3SJhEfxv48euadKgrIX3Z79ruQFSQ"
            "Oc9LUrDjR%2B4SoWAJqK%2BGX8Q3vPSjsLxhqhEMWd6U4TXcM7ku3gxMbzqfT8NDg%3D"
        )
        session_token = urllib.parse.unquote(quoted_session_token)
    else:
        session_token = ""
    try:
        object_storage_config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            bucket_host="examplebucket.s3.amazonaws.com",
            bucket_region="us-east-1",
            session_token=session_token,
        )
    except AttributeError:
        object_storage_config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            bucket_name="examplebucket",
            bucket_region="us-east-1",
            session_token=session_token,
        )
        object_storage_config.bucket_host = "examplebucket.s3.amazonaws.com"
    return object_storage_config


@pytest.fixture(params=(False, True))
def object_storage_config_for_presigned_post_example(
    request: pytest.FixtureRequest,
) -> fastenv.cloud.object_storage.ObjectStorageConfig:
    """Provide a single cloud configuration instance with data from the AWS docs.

    https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html

    The virtual-hosted-style URL in this example lacks a region. The docs mix
    path-style URLs (`s3.amazonaws.com/examplebucket`), virtual-hosted-style URLs
    without regions (`examplebucket.s3.amazonaws.com`), and virtual-hosted-style
    URLs with regions (`examplebucket.s3.us-east-1.amazonaws.com`).
    """
    use_session_token: bool = getattr(request, "param")
    if use_session_token is True:
        # docs only provide the quoted session token
        quoted_session_token = (
            "IQoJb3JpZ2luX2VjEMv%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJGME"
            "QCIBSUbVdj9YGs2g0HkHsOHFdkwOozjARSKHL987NhhOC8AiBPepRU1obMvIbGU0T%2BWp"
            "hFPgK%2Fqpxaf5Snvm5M57XFkCqlAgjz%2F%2F%2F%2F%2F%2F%2F%2F%2F%2F8BEAAaDD"
            "Q3MjM4NTU0NDY2MCIM83pULBe5%2F%2BNm1GZBKvkBVslSaJVgwSef7SsoZCJlfJ56weYl"
            "3QCwEGr2F4BmCZZyFpmWEYzWnhNK1AnHMj5nkfKlKBx30XAT5PZGVrmq4Vkn9ewlXQy1Iu"
            "3QJRi9Tdod8Ef9%2FyajTaUGh76%2BF5u5a4O115jwultOQiKomVwO318CO4l8lv%2F3Hh"
            "MOkpdanMXn%2B4PY8lvM8RgnzSu90jOUpGXEOAo%2F6G8OqlMim3%2BZmaQmasn4VYRvES"
            "Ed7O72QGZ3%2BvDnDVnss0lSYjlv8PP7IujnvhZRnj0WoeOyMe1lL0wTG%2Fa9usH5hE52"
            "w%2FYUJccOn0OaZuyROuVsRV4Q70sbWQhUvYUt%2B0tUMKzm8vsFOp4BaNZFqobbjtb36Y"
            "92v%2Bx5kY6i0s8QE886jJtUWMP5ldMziClGx3p0mN5dzsYlM3GyiJ%2FO1mWkPQDwg3mt"
            "SpOA9oeeuAMPTA7qMqy9RNuTKBDSx9EW27wvPzBum3SJhEfxv48euadKgrIX3Z79ruQFSQ"
            "Oc9LUrDjR%2B4SoWAJqK%2BGX8Q3vPSjsLxhqhEMWd6U4TXcM7ku3gxMbzqfT8NDg%3D"
        )
        session_token = urllib.parse.unquote(quoted_session_token)
    else:
        session_token = ""
    try:
        object_storage_config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            bucket_host="sigv4examplebucket.s3.amazonaws.com",
            bucket_name="sigv4examplebucket",
            bucket_region="us-east-1",
            session_token=session_token,
        )
    except AttributeError:
        object_storage_config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            bucket_name="sigv4examplebucket",
            bucket_region="us-east-1",
            session_token=session_token,
        )
        object_storage_config.bucket_host = "sigv4examplebucket.s3.amazonaws.com"
    return object_storage_config


@pytest.fixture(scope="function")
def object_storage_client_upload_policy_from_presigned_post_example() -> UploadPolicy:
    """Provide the presigned POST upload policy from the example in the AWS docs.

    https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html
    """
    return {
        "expiration": "2015-12-30T12:00:00.000Z",
        "conditions": [
            {"bucket": "sigv4examplebucket"},
            ["starts-with", "$key", "user/user1/"],
            {"acl": "public-read"},
            {
                "success_action_redirect": (
                    "http://sigv4examplebucket.s3.amazonaws.com/successful_upload.html"
                )
            },
            ["starts-with", "$Content-Type", "image/"],
            {"x-amz-meta-uuid": "14365123651274"},
            {"x-amz-server-side-encryption": "AES256"},
            ["starts-with", "$x-amz-meta-tag", ""],
            {
                "x-amz-credential": (
                    "AKIAIOSFODNN7EXAMPLE/20151229/us-east-1/s3/aws4_request"
                )
            },
            {"x-amz-algorithm": "AWS4-HMAC-SHA256"},
            {"x-amz-date": "20151229T000000Z"},
        ],
    }


@pytest.fixture(scope="session")
def object_storage_client_upload_prefix() -> str:
    """Provide a bucket prefix for uploading to cloud object storage.

    The prefix includes the test session time as a formatted string. The string
    will be formatted like "2022-01-01-220123-UTC". There is also a random text
    string added, to ensure that each test run has a unique prefix.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    now_string = now.strftime("%Y-%m-%d-%H%M%S-%Z")
    hex_prefix = secrets.token_hex()[:10]
    return f"uploads/{now_string}-{hex_prefix}"


_dotenv_args: tuple[tuple[str, str, str], ...] = (
    (
        "AWS_ACCESS_KEY_ID_EXAMPLE=AKIAIOSFODNN7EXAMPLE",
        "AWS_ACCESS_KEY_ID_EXAMPLE",
        "AKIAIOSFODNN7EXAMPLE",
    ),
    (
        "AWS_SECRET_ACCESS_KEY_EXAMPLE=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE",
        "AWS_SECRET_ACCESS_KEY_EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE",
    ),
    (
        "CSV_VARIABLE=comma,separated,value",
        "CSV_VARIABLE",
        "comma,separated,value",
    ),
    (
        "EMPTY_VARIABLE= \n",
        "EMPTY_VARIABLE",
        "",
    ),
    (
        "INLINE_COMMENT=no_comment  # inline comment ",
        "INLINE_COMMENT",
        "no_comment",
    ),
    (
        'JSON_EXAMPLE=\'{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}\'',
        "JSON_EXAMPLE",
        '{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}',
    ),
    (
        "PASSWORD='64w2Q$!&,,[EXAMPLE'",
        "PASSWORD",
        "64w2Q$!&,,[EXAMPLE",
    ),
    (
        "QUOTES_AND_WHITESPACE=\"' text and spaces '\"",
        "QUOTES_AND_WHITESPACE",
        "text and spaces",
    ),
    (
        "URI_TO_DIRECTORY=~/dev",
        "URI_TO_DIRECTORY",
        "~/dev",
    ),
    (
        "URI_TO_S3_BUCKET=s3://mybucket/.env",
        "URI_TO_S3_BUCKET",
        "s3://mybucket/.env",
    ),
    (
        "URI_TO_SQLITE_DB=sqlite:////path/to/db.sqlite",
        "URI_TO_SQLITE_DB",
        "sqlite:////path/to/db.sqlite",
    ),
    (
        "URL_EXAMPLE=https://start.duckduckgo.com/",
        "URL_EXAMPLE",
        "https://start.duckduckgo.com/",
    ),
)

_dotenv_kwargs: tuple[tuple[dict[str, str], str, str], ...] = tuple(
    ({expected_key: expected_value}, expected_key, expected_value)
    for _, expected_key, expected_value in _dotenv_args
)

_input_args: tuple[str, ...] = tuple(i[0] for i in _dotenv_args)

_input_kwargs: dict[str, str] = {i[1]: i[2] for i in _dotenv_args}


@pytest.fixture(scope="session")
def dotenv_args() -> tuple[tuple[str, str, str], ...]:
    """Provide example positional input arguments and their expected outputs."""
    return _dotenv_args


@pytest.fixture(params=_dotenv_args, scope="session")
def dotenv_arg(request: pytest.FixtureRequest) -> tuple[str, str, str]:
    """Parametrize the example positional input arguments and their expected outputs.

    Each item is a three-tuple which contains:

    0. A `"key=value"` string that will be passed to a `DotEnv` instance
       as a positional argument to set a variable
    1. The variable key that is expected to be set
    2. The variable value that is expected to be set

    The tuple is usually unpacked within each test:
    `input_arg, output_key, output_value = dotenv_arg`.

    This is a parametrized fixture. When the fixture is used in a test, the test
    will be automatically parametrized, running once for each fixture parameter.
    https://docs.pytest.org/en/latest/how-to/fixtures.html
    """
    request_param: tuple[str, str, str] = getattr(request, "param")
    return request_param


@pytest.fixture(scope="session")
def dotenv_kwargs() -> tuple[tuple[dict[str, str], str, str], ...]:
    """Provide example keyword input arguments and their expected outputs."""
    return _dotenv_kwargs


@pytest.fixture(params=_dotenv_kwargs, scope="session")
def dotenv_kwarg(request: pytest.FixtureRequest) -> tuple[dict[str, str], str, str]:
    """Parametrize the example keyword input arguments and their expected outputs.

    Each item is a three-tuple which contains:

    0. A `{key: value}` dictionary that will be passed to a `DotEnv` instance
       as a positional argument to set a variable
    1. The variable key that is expected to be set
    2. The variable value that is expected to be set

    The tuple is usually unpacked within each test:
    `input_kwarg, output_key, output_value = dotenv_kwarg`

    This is a parametrized fixture. When the fixture is used in a test, the test
    will be automatically parametrized, running once for each fixture parameter.
    https://docs.pytest.org/en/latest/how-to/fixtures.html
    """
    request_param: tuple[dict[str, str], str, str] = getattr(request, "param")
    return request_param


@pytest.fixture(
    params=(
        ({"dict": {"key": "value"}}, "DICT", "{'key': 'value'}"),
        ({"int": 123}, "INT", "123"),
        ({"list": [1, 2, 3]}, "LIST", "[1, 2, 3]"),
    ),
    scope="session",
)
def dotenv_kwarg_incorrect_type(
    request: pytest.FixtureRequest,
) -> tuple[dict[str, Any], str, str]:
    """Provide example keyword arguments with incorrect types.

    `DotEnv` instances convert non-string keyword arguments ("kwargs") to strings.

    Each item is a three-tuple which contains:

    0. A `{key: value}` dictionary that will be passed to a `DotEnv` instance
       as a positional argument to set a variable
    1. The variable key that is expected to be set
    2. The variable value that is expected to be set

    The tuple is usually unpacked within each test:
    `input_kwarg, output_key, output_value = dotenv_kwarg_incorrect_type`

    This is a parametrized fixture. When the fixture is used in a test, the test
    will be automatically parametrized, running once for each fixture parameter.
    https://docs.pytest.org/en/latest/how-to/fixtures.html
    """
    request_param: tuple[dict[str, Any], str, str] = getattr(request, "param")
    return request_param


@pytest.fixture(scope="session")
def input_args() -> tuple[str, ...]:
    """Provide example positional input arguments.

    An `input_arg` as defined here is just the `"key=value"` string that will be
    passed to a `DotEnv` instance as a positional argument to set a variable.

    This fixture is provided separately so that all the positional arguments can
    be passed in to a `DotEnv` instance simultaneously, by unpacking the tuple.
    """
    return _input_args


@pytest.fixture(params=({"key": "value"}, 123, [1, 2, 3]), scope="session")
def input_arg_incorrect_type(
    request: pytest.FixtureRequest,
) -> dict[str, str] | int | list[int]:
    """Provide example positional arguments with incorrect types.

    Environment variable keys and values should be strings. If non-string positional
    arguments ("args") are passed to a `DotEnv` instance, it will raise a `TypeError`,
    rather than attempting to handle the args. This is because args can be used either
    to get or set variables, and it can be challenging to infer the user's intent when
    non-string args are used in this situation.

    This is a parametrized fixture. When the fixture is used in a test, the test
    will be automatically parametrized, running once for each fixture parameter.
    https://docs.pytest.org/en/latest/how-to/fixtures.html
    """
    request_param: dict[str, str] | int | list[int] = getattr(request, "param")
    return request_param


@pytest.fixture(scope="session")
def input_kwargs() -> dict[str, str]:
    """Provide example keyword input arguments.

    The `input_kwargs` return value is a dictionary of all test `key: value` pairs.

    This fixture is provided separately so that all the keyword arguments can
    be passed in to a `DotEnv` instance simultaneously, by unpacking the dictionary.
    """
    return _input_kwargs


@pytest.fixture(scope="session")
def env_str(input_args: tuple[str, ...]) -> str:
    """Specify environment variables within a string for testing."""
    return "\n".join(input_args)


@pytest.fixture(scope="session")
def env_bytes(env_str: str) -> bytes:
    """Specify environment variables as bytes for testing."""
    env_str_with_byte_variable = (
        "# This content was provided to fastenv as bytes prior to upload.\n"
        "BYTE_VARIABLE_KEY=byte_variable_value\n\n"
    ) + env_str
    return env_str_with_byte_variable.encode()


@pytest.fixture(scope="session")
def env_str_unsorted() -> str:
    """Specify unsorted environment variables within a string for testing."""
    return "KEY3=value3\nKEY1=value1\nKEY2=value2\n"


@pytest.fixture(scope="session")
def env_str_multi() -> tuple[str, ...]:
    """Specify environment variables within multiple strings for testing."""
    return tuple(
        (
            f"AWS_ACCESS_KEY_ID_EXAMPLE=AKIAIOSMULTI{i}EXAMPLE\n"
            f"AWS_SECRET_ACCESS_KEY_EXAMPLE=wJalrXUtnFEMI/K7MDENG/bPMULTI{i}EXAMPLE\n"
            f"CSV_VARIABLE=multi,{i},example\n"
            f"MULTI_{i}_VARIABLE=multi_{i}_value"
        )
        for i in range(3)
    )


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file(
    env_str: str, tmp_path_factory: pytest.TempPathFactory
) -> anyio.Path:
    """Create .env.testing file with environment variables."""
    tmp_dir = tmp_path_factory.mktemp("env_files")
    tmp_file = anyio.Path(tmp_dir) / ".env.testing"
    _ = await tmp_file.write_text(env_str)
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_unsorted(env_file: anyio.Path, env_str_unsorted: str) -> anyio.Path:
    """Create .env file with unsorted environment variables."""
    tmp_file = env_file.parent / ".env.unsorted"
    _ = await tmp_file.write_text(env_str_unsorted)
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_empty(env_file: anyio.Path) -> anyio.Path:
    """Create .env file with no variables."""
    tmp_file = env_file.parent / ".env.empty"
    _ = await tmp_file.write_text("\n")
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_child_dir(env_file: anyio.Path) -> anyio.Path:
    """Create child directories to test `find_dotenv`."""
    starting_dir = anyio.Path(env_file.parent) / "child1" / "child2" / "child3"
    await starting_dir.mkdir(parents=True, exist_ok=False)
    return starting_dir


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_files_in_same_dir(
    env_file: anyio.Path,
    env_str_multi: tuple[str, ...],
) -> list[anyio.Path]:
    """Create multiple .env files in a single directory to test `load_dotenv`."""
    env_files: list[anyio.Path] = [env_file]
    for i, env_str in enumerate(env_str_multi):
        new_file = env_file.parent / f".env.child{i}"
        _ = await new_file.write_text(env_str)
        env_files.append(new_file)
    return env_files


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_files_in_child_dirs(
    env_file_child_dir: anyio.Path,
    env_str_multi: tuple[str, ...],
) -> list[anyio.Path]:
    """Create multiple .env files in child directories to test `load_dotenv`."""
    env_files: list[anyio.Path] = []
    for i, env_str in enumerate(env_str_multi):
        new_file = env_file_child_dir.parents[i] / f".env.child{i}"
        _ = await new_file.write_text(env_str)
        env_files.append(new_file)
    return env_files


@pytest.fixture(scope="session")
def env_files_output() -> tuple[tuple[str, str], ...]:
    """Define the variable keys and values that are expected to be set
    when the test .env files are loaded into `DotEnv` instances.

    The test .env files are generated by writing the output of the `env_str_multi`
    fixture into multiple files, then loading the files.

    Each item is a two-tuple which contains:

    0. The variable key that is expected to be set
    1. The variable value that is expected to be set

    Variable values should be updated in left-to-right order, so if `CSV_VARIABLE`
    is defined multiple times, the last file loaded will determine the value that
    is set (`multi,2,example` here).
    """
    return (
        ("AWS_ACCESS_KEY_ID_EXAMPLE", "AKIAIOSMULTI2EXAMPLE"),
        ("AWS_SECRET_ACCESS_KEY_EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPMULTI2EXAMPLE"),
        ("CSV_VARIABLE", "multi,2,example"),
        ("MULTI_0_VARIABLE", "multi_0_value"),
        ("MULTI_1_VARIABLE", "multi_1_value"),
        ("MULTI_2_VARIABLE", "multi_2_value"),
    )


@pytest.fixture(scope="session")
def env_file_object_additional_input() -> dict[str, str]:
    """Add a variable that will only be added to files in object storage."""
    return {
        "OBJECT_STORAGE_VARIABLE": "DUDE!!! This variable came from object storage!"
    }


@pytest.fixture(scope="session")
def env_file_object_expected_output(
    env_file_object_additional_input: dict[str, str], input_kwargs: dict[str, str]
) -> dict[str, str]:
    """Define the variable keys and values that are expected to be set
    when test .env files are loaded from cloud object storage.

    The test .env files in object storage have the same values from the `env_file`
    fixture, with additional variables specific to the cloud objects.
    """
    return {**input_kwargs, **env_file_object_additional_input}
