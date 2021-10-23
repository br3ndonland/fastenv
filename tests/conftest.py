from __future__ import annotations

import datetime
import os
import secrets
from collections import namedtuple

import anyio
import pytest

import fastenv.cloud


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Specify the back-end for pytest to use when running async functions
    with [AnyIO](https://anyio.readthedocs.io/en/stable/testing.html).
    """
    return "asyncio"


CloudParams = namedtuple(
    "CloudParams",
    (
        "access_key_variable",
        "secret_key_variable",
        "session_token_variable",
        "bucket_host_variable",
        "bucket_region_variable",
    ),
)

_cloud_params_aws_session = CloudParams(
    access_key_variable="AWS_SESSION_ACCESS_KEY",
    secret_key_variable="AWS_SESSION_SECRET_KEY",
    session_token_variable="AWS_SESSION_TOKEN",
    bucket_host_variable="AWS_S3_BUCKET_DOMAIN",
    bucket_region_variable="AWS_S3_REGION",
)
_cloud_params_aws_static = CloudParams(
    access_key_variable="AWS_FASTENV_ACCESS_KEY",
    secret_key_variable="AWS_FASTENV_SECRET_KEY",
    session_token_variable="",
    bucket_host_variable="AWS_S3_BUCKET_DOMAIN",
    bucket_region_variable="AWS_S3_REGION",
)
_cloud_params_backblaze_static = CloudParams(
    access_key_variable="BACKBLAZE_FASTENV_ACCESS_KEY",
    secret_key_variable="BACKBLAZE_FASTENV_SECRET_KEY",
    session_token_variable="",
    bucket_host_variable="BACKBLAZE_B2_BUCKET_DOMAIN",
    bucket_region_variable="BACKBLAZE_B2_REGION",
)


@pytest.fixture(
    params=(
        _cloud_params_aws_session,
        _cloud_params_aws_static,
        _cloud_params_backblaze_static,
    ),
    scope="session",
)
def cloud_config(request: pytest.FixtureRequest) -> fastenv.cloud.S3Config:
    """Provide cloud configurations for testing.

    This fixture will retrieve cloud credentials from environment variables, then
    use the credentials to return instances of `fastenv.cloud.S3Config` for testing.

    This is a parametrized fixture. When the fixture is used in a test, the test
    will be automatically parametrized, running once for each fixture parameter.
    https://docs.pytest.org/en/latest/how-to/fixtures.html
    """
    request_param = getattr(request, "param")
    access_key = os.getenv(request_param.access_key_variable, "")
    secret_key = os.getenv(request_param.secret_key_variable, "")
    session_token = (
        os.getenv(request_param.session_token_variable)
        if request_param.session_token_variable
        else ""
    )
    bucket_host = os.getenv(request_param.bucket_host_variable, "")
    bucket_region = os.getenv(request_param.bucket_region_variable, "us-east-2")
    if not access_key or not secret_key or session_token is None:
        pytest.skip("Required cloud credentials not present.")
    return fastenv.cloud.S3Config(
        aws_access_key=access_key,
        aws_secret_key=secret_key,
        aws_region=bucket_region,
        aws_s3_bucket=bucket_host,
        aws_session_token=str(session_token),
    )


@pytest.fixture(scope="session")
def cloud_config_aws_static() -> fastenv.cloud.S3Config:
    """Provide a single cloud configuration instance for testing.

    Rather than parametrizing all the cloud configurations, this fixture sets up
    a single instance of `aioaws.s3.S3Config` for testing a specific configuration.

    This fixture also tests the effect of providing the bucket as a bucket name alone,
    instead of as a domain. Bucket names can be used for AWS S3, but not Backblaze B2,
    because of how `aioaws.core.AwsClient` determines the `host` attribute.
    """
    access_key = os.getenv(_cloud_params_aws_static.access_key_variable, "")
    secret_key = os.getenv(_cloud_params_aws_static.secret_key_variable, "")
    if not access_key or not secret_key:
        pytest.skip("Required cloud credentials not present.")
    bucket_host = os.getenv(_cloud_params_aws_static.bucket_host_variable, "")
    bucket_name = str(bucket_host).split(sep=".", maxsplit=1)[0]
    bucket_region = os.getenv(
        _cloud_params_aws_static.bucket_region_variable, "us-east-2"
    )
    return fastenv.cloud.S3Config(
        aws_access_key=access_key,
        aws_secret_key=secret_key,
        aws_region=bucket_region,
        aws_s3_bucket=bucket_name,
    )


@pytest.fixture(scope="session")
def cloud_config_backblaze_static() -> fastenv.cloud.S3Config:
    """Provide a single cloud configuration instance for testing.

    Rather than parametrizing all the cloud configurations, this fixture sets up
    a single instance of `aioaws.s3.S3Config` for testing a specific configuration.
    """
    access_key = os.getenv(_cloud_params_backblaze_static.access_key_variable, "")
    secret_key = os.getenv(_cloud_params_backblaze_static.secret_key_variable, "")
    if not access_key or not secret_key:
        pytest.skip("Required cloud credentials not present.")
    bucket_host = os.getenv(_cloud_params_backblaze_static.bucket_host_variable, "")
    bucket_host = os.getenv(_cloud_params_backblaze_static.bucket_host_variable, "")
    bucket_region = os.getenv(_cloud_params_backblaze_static.bucket_region_variable, "")
    return fastenv.cloud.S3Config(
        aws_access_key=access_key,
        aws_secret_key=secret_key,
        aws_region=bucket_region,
        aws_s3_bucket=bucket_host,
    )


@pytest.fixture(scope="session")
def cloud_config_incorrect() -> fastenv.cloud.S3Config:
    """Provide a single cloud configuration instance for testing.

    Rather than parametrizing all the cloud configurations, this fixture sets up
    a single instance of `aioaws.s3.S3Config` for testing a specific configuration.

    This particular configuration is provided for testing authorization errors.
    """
    bucket_host = os.getenv("AWS_S3_BUCKET_DOMAIN")
    bucket_name = str(bucket_host).split(sep=".", maxsplit=1)[0]
    bucket_region = os.getenv("AWS_S3_REGION", "us-east-2")
    return fastenv.cloud.S3Config(
        aws_access_key="AKIAIOSFODNN7EXAMPLE",
        aws_secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE",
        aws_region=bucket_region,
        aws_s3_bucket=bucket_name,
    )


@pytest.fixture(scope="session")
def cloud_client_upload_prefix() -> str:
    """Provide a bucket prefix for uploading to cloud object storage.

    The prefix includes the test session time as a formatted string. The string
    will be formatted like "2022-01-01-220123-UTC". There is also a random text
    string added, to ensure that each test run has a unique prefix.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    now_string = now.strftime("%Y-%m-%d-%H%M%S-%Z")
    hex_prefix = secrets.token_hex()[:10]
    return f"uploads/{now_string}-{hex_prefix}"


@pytest.fixture(scope="session")
def cloud_client_backblaze_b2_upload_url_response(
    cloud_config_backblaze_static: fastenv.cloud.S3Config,
) -> fastenv.cloud.httpx.Response:
    """Provide a mock `httpx.Response` from a call to Backblaze `b2_get_upload_url`.

    https://www.backblaze.com/b2/docs/b2_get_upload_url.html
    """
    authorization_token = (
        f"4_{cloud_config_backblaze_static.aws_access_key}"
        "_01a10000_fd9b00_upld_a_27_character_alphanumeric="
    )
    bucket_id = "123456789012123456789012"
    upload_url = (
        "https://pod-000-1111-01.backblaze.com/b2api/v2/"
        f"b2_upload_file/{bucket_id}/c001_v0001111_t0030"
    )
    upload_url_response_text = (
        "{"
        f'\n  "authorizationToken": "{authorization_token}",'
        f'\n  "bucketId": "{bucket_id}",'
        f'\n  "uploadUrl": "{upload_url}"'
        "\n}\n"
    )
    return fastenv.cloud.httpx.Response(200, text=upload_url_response_text)


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
    for input_arg, expected_key, expected_value in _dotenv_args
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
    return getattr(request, "param")


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
    return getattr(request, "param")


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
) -> tuple[dict, str, str]:
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
    return getattr(request, "param")


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
def input_arg_incorrect_type(request: pytest.FixtureRequest) -> dict | int | list:
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
    return getattr(request, "param")


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
    await tmp_file.write_text(env_str)
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_unsorted(env_file: anyio.Path, env_str_unsorted: str) -> anyio.Path:
    """Create .env file with unsorted environment variables."""
    tmp_file = env_file.parent / ".env.unsorted"
    await tmp_file.write_text(env_str_unsorted)
    return tmp_file


@pytest.fixture(scope="session")
@pytest.mark.anyio
async def env_file_empty(env_file: anyio.Path) -> anyio.Path:
    """Create .env file with no variables."""
    tmp_file = env_file.parent / ".env.empty"
    await tmp_file.write_text("\n")
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
        await new_file.write_text(env_str)
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
        await new_file.write_text(env_str)
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
