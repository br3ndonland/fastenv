from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

import fastenv.cloud
import fastenv.dotenv
from tests.test_dotenv import variable_is_set


class TestS3Config:
    """Test instantiation of `class S3Config`."""

    example_access_key = "AKIAIOSFODNN7EXAMPLE"
    example_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE"
    example_access_key_for_session_token = "ASIAIOSFODNN7EXAMPLE"
    example_secret_key_for_session_token = "AAAAiAt0AAv5AAi5uAAsAAAAoA15AfAz7EXAMPLE"
    example_session_token = (
        "A756CharacterString//////////wAaAAAzAAAhc1AtAAAAAAAAAAAAo28gA+A"
        "08AeAhlj1AA/ifo7As+9A+AnAAAAAx44AAgAgAAmA+Amtib1nAAAAAsc8Ak4Ac5"
        "1ivAbdAAA11uqAAAAqowAAw///////////AAAAAgw4AAA2AAAzAAA4AjAiAAAAk"
        "1pAbcdAAjrAoyr1AAAuiAqbwrAAA9AgAA8AnxvAAmAwdi/A9AsAvnAo5nqAk4AA"
        "isAA9nc6AAA1gA1AAAAmAA0dAAxebsoA8cAAmA+AAAp2w1AA11AAyA9A/wnAAn+"
        "bztAAw8/9y70AAAd+AAg5aAmA59a2A+zAnlxkAr0jbA5846AAA+AmsqAc9qAAvA"
        "e0A+bAlAAuqArAquoAAdApyal/wsAAlfmAsAA7Ai9AAAjt4qj0A4AcAvaudAzA9"
        "17rbAfAlmAmfAAAAAAfAzdk2+0+A2m1Acp0bmgAAAlAAcxAAA9A66AhAoAApAAa"
        "19jnAA7AAbxA0A1+jmA/AAgA8qwA+AowksA4jAA6nAAA/AvacpAackw4xsAj9aA"
        "dAtnAba6uAjqoAhAaAAAAdn5AA8AA6jhAsArAA7zA2A+AAAvlcpwmfA+AiAA/1A"
        "AdAtyAArnAAA0iAAA6jfyAAzAAA7AeAmAnesAAAA0AhAAweiA9A8AythuftAhto"
        "AA+7fAuvs1wiAA6w+m6AcsndAnfw55oA1A9wAfAn82Az7bAvA9u/AfAeEXAMPLE"
    )
    example_bucket_name = "mybucket"

    def config_is_correct(
        self, config: fastenv.cloud.S3Config, should_have_session_token: bool = False
    ) -> bool:
        """Assert that an `S3Config` instance has the expected attribute values."""
        if should_have_session_token:
            assert config.aws_access_key == self.example_access_key_for_session_token
            assert config.aws_secret_key == self.example_secret_key_for_session_token
            assert config.aws_session_token == self.example_session_token
        else:
            assert config.aws_access_key == self.example_access_key
            assert config.aws_secret_key == self.example_secret_key
            assert not config.aws_session_token
        assert config.aws_region == "us-east-1"
        assert config.aws_s3_bucket == self.example_bucket_name
        return True

    @pytest.mark.parametrize("should_have_session_token", (False, True))
    def test_config_from_environment_variables(
        self, mocker: MockerFixture, should_have_session_token: bool
    ) -> None:
        """Instantiate `class S3Config`, allowing the class to detect the default
        AWS environment variables, and assert that the correct values are set.
        """
        environ = mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        if should_have_session_token:
            environ["AWS_ACCESS_KEY_ID"] = self.example_access_key_for_session_token
            environ["AWS_SECRET_ACCESS_KEY"] = self.example_secret_key_for_session_token
            environ["AWS_SESSION_TOKEN"] = self.example_session_token
        else:
            environ["AWS_ACCESS_KEY_ID"] = self.example_access_key
            environ["AWS_SECRET_ACCESS_KEY"] = self.example_secret_key
        config = fastenv.cloud.S3Config(aws_s3_bucket=self.example_bucket_name)
        assert self.config_is_correct(
            config, should_have_session_token=should_have_session_token
        )

    def test_config_from_kwargs(self, mocker: MockerFixture) -> None:
        """Instantiate `class S3Config` with keyword arguments
        and assert that the correct values are set.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        config = fastenv.cloud.S3Config(
            aws_access_key=self.example_access_key,
            aws_secret_key=self.example_secret_key,
            aws_s3_bucket=self.example_bucket_name,
        )
        assert self.config_is_correct(config)

    def test_config_error_no_bucket(self, mocker: MockerFixture) -> None:
        """Instantiate `class S3Config` without a bucket argument
        and assert that a `RuntimeError` is raised.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        with pytest.raises(RuntimeError) as e:
            fastenv.cloud.S3Config(
                aws_access_key=self.example_access_key,
                aws_secret_key=self.example_secret_key,
            )
        assert "S3 bucket not present" in str(e.value)

    def test_config_error_no_credentials(self, mocker: MockerFixture) -> None:
        """Instantiate `class S3Config` without all necessary credentials
        and assert that a `RuntimeError` is raised.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        with pytest.raises(RuntimeError) as e:
            fastenv.cloud.S3Config(
                aws_access_key=self.example_access_key,
                aws_s3_bucket=self.example_bucket_name,
            )
        assert "cloud credentials not present" in str(e.value)


class TestS3Client:
    """Test `class S3Client` and its methods."""

    key = ".env.testing"

    def test_client_instantiation_error(self, mocker: MockerFixture) -> None:
        """Attempt to instantiate `S3Client` without providing a bucket,
        and assert that a `RuntimeError` is raised.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        with pytest.raises(RuntimeError) as e:
            fastenv.cloud.S3Client()
        assert "not present" in str(e.value)

    @pytest.mark.anyio
    async def test_download_to_file_with_cloud_config(
        self,
        cloud_config: fastenv.cloud.S3Config,
        env_file: fastenv.cloud.anyio.Path,
        env_file_object_expected_output: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Download a file from cloud object storage by providing an instance of
        `S3Config`, load the file, and assert that all expected variables are set.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        environ = mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)
        destination = env_file.parent / f".env.{cloud_config.aws_access_key}"
        env_file_download = await cloud_client.download(self.key, destination)
        dotenv = await fastenv.dotenv.load_dotenv(env_file_download)
        assert dotenv.source == env_file_download
        for expected_key, expected_value in env_file_object_expected_output.items():
            assert variable_is_set(dotenv, environ, expected_key, expected_value)
        logger.info.assert_called_once_with(
            f"fastenv loaded {self.key} from {cloud_config.aws_s3_bucket} "
            f"and wrote the contents to {destination}"
        )

    @pytest.mark.anyio
    async def test_download_to_file_with_bucket_name(
        self,
        cloud_config_aws_static: fastenv.cloud.S3Config,
        env_file: fastenv.cloud.anyio.Path,
        env_file_object_expected_output: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Download a file from cloud object storage by providing the bucket name
        and region, load the file, and assert that all expected variables are set.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        environ = mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        environ["AWS_ACCESS_KEY_ID"] = cloud_config_aws_static.aws_access_key
        environ["AWS_SECRET_ACCESS_KEY"] = cloud_config_aws_static.aws_secret_key
        expected_bucket_host = (
            f"{cloud_config_aws_static.aws_s3_bucket}.s3."
            f"{cloud_config_aws_static.aws_region}.amazonaws.com"
        )
        cloud_client = fastenv.cloud.S3Client(config=cloud_config_aws_static)
        destination = env_file.parent / ".env.testing-object-storage-bucket-name"
        env_file_download = await cloud_client.download(self.key, destination)
        dotenv = await fastenv.dotenv.load_dotenv(env_file_download)
        assert dotenv.source == env_file_download
        for expected_key, expected_value in env_file_object_expected_output.items():
            assert variable_is_set(dotenv, environ, expected_key, expected_value)
        logger.info.assert_called_once_with(
            f"fastenv loaded {self.key} from {expected_bucket_host} "
            f"and wrote the contents to {destination}"
        )

    @pytest.mark.anyio
    async def test_download_to_string_with_cloud_config(
        self,
        cloud_config: fastenv.cloud.S3Config,
        env_file_object_expected_output: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Download a file from cloud object storage by providing an instance of
        `S3Config`, load the string, and assert that all expected variables are set.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        environ = mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)
        env_file_contents = await cloud_client.download(self.key)
        assert isinstance(env_file_contents, str)
        dotenv = fastenv.dotenv.DotEnv(env_file_contents)
        for expected_key, expected_value in env_file_object_expected_output.items():
            assert variable_is_set(dotenv, environ, expected_key, expected_value)
        logger.info.assert_called_once_with(
            f"fastenv loaded {self.key} from {cloud_config.aws_s3_bucket}"
        )

    @pytest.mark.anyio
    async def test_download_to_string_with_bucket_name(
        self,
        cloud_config_aws_static: fastenv.cloud.S3Config,
        env_file_object_expected_output: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Download a file from cloud object storage by providing the bucket name
        and region, load the string, and assert that all expected variables are set.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        environ = mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        environ["AWS_ACCESS_KEY_ID"] = cloud_config_aws_static.aws_access_key
        environ["AWS_SECRET_ACCESS_KEY"] = cloud_config_aws_static.aws_secret_key
        expected_bucket_host = (
            f"{cloud_config_aws_static.aws_s3_bucket}.s3."
            f"{cloud_config_aws_static.aws_region}.amazonaws.com"
        )
        cloud_client = fastenv.cloud.S3Client(config=cloud_config_aws_static)
        env_file_contents = await cloud_client.download(self.key)
        assert isinstance(env_file_contents, str)
        dotenv = fastenv.dotenv.DotEnv(env_file_contents)
        for expected_key, expected_value in env_file_object_expected_output.items():
            assert variable_is_set(dotenv, environ, expected_key, expected_value)
        logger.info.assert_called_once_with(
            f"fastenv loaded {self.key} from {expected_bucket_host}"
        )

    @pytest.mark.anyio
    async def test_download_error(
        self, cloud_config: fastenv.cloud.S3Config, mocker: MockerFixture
    ) -> None:
        """Attempt to download a non-existent file from cloud object storage,
        and assert that a `RequestError` is raised with the expected status code.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)
        with pytest.raises(fastenv.cloud.aioaws.core.RequestError) as e:
            await cloud_client.download(key=f"{self.key}-does-not-exist")
        assert e.value.response.status_code == 404
        assert cloud_config.aws_s3_bucket in str(e.value)
        assert "fastenv error" in logger.error.call_args.args[0]
        assert "RequestError" in logger.error.call_args.args[0]

    @pytest.mark.anyio
    async def test_upload_from_file_with_cloud_config(
        self,
        # TODO: https://github.com/samuelcolvin/aioaws/pull/24
        # cloud_config: fastenv.cloud.S3Config,
        cloud_config_aws_static: fastenv.cloud.S3Config,
        cloud_client_upload_prefix: str,
        env_file: fastenv.cloud.anyio.Path,
        mocker: MockerFixture,
    ) -> None:
        """Upload a file to cloud object storage, and assert that the
        expected logger message is provided after a successful upload.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        # TODO: https://github.com/samuelcolvin/aioaws/pull/24
        cloud_config = cloud_config_aws_static  # remove this line
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)
        bucket_key = (
            f"{cloud_client_upload_prefix}/.env.from-file."
            f"{cloud_config.aws_access_key}"
        )
        await cloud_client.upload(key=bucket_key, source=env_file)
        logger.info.assert_called_once_with(
            f"fastenv loaded {env_file} and wrote the contents to"
            f" {cloud_config.aws_s3_bucket}/{bucket_key}"
        )

    @pytest.mark.anyio
    async def test_upload_from_string_with_cloud_config(
        self,
        # TODO: https://github.com/samuelcolvin/aioaws/pull/24
        # cloud_config: fastenv.cloud.S3Config,
        cloud_config_aws_static: fastenv.cloud.S3Config,
        cloud_client_upload_prefix: str,
        env_str: str,
        mocker: MockerFixture,
    ) -> None:
        """Upload a string to cloud object storage, and assert that the
        expected logger message is provided after a successful upload.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        # TODO: https://github.com/samuelcolvin/aioaws/pull/24
        cloud_config = cloud_config_aws_static  # remove this line
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)
        bucket_key = (
            f"{cloud_client_upload_prefix}/.env.from-string."
            f"{cloud_config.aws_access_key}"
        )
        await cloud_client.upload(key=bucket_key, source=env_str)
        logger.info.assert_called_once_with(
            f"fastenv loaded the provided string and wrote the contents to"
            f" {cloud_config.aws_s3_bucket}/{bucket_key}"
        )

    @pytest.mark.anyio
    async def test_upload_from_bytes_with_cloud_config(
        self,
        # TODO: https://github.com/samuelcolvin/aioaws/pull/24
        # cloud_config: fastenv.cloud.S3Config,
        cloud_config_aws_static: fastenv.cloud.S3Config,
        cloud_client_upload_prefix: str,
        env_bytes: bytes,
        mocker: MockerFixture,
    ) -> None:
        """Upload bytes to cloud object storage, and assert that the
        expected logger message is provided after a successful upload.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        # TODO: https://github.com/samuelcolvin/aioaws/pull/24
        cloud_config = cloud_config_aws_static  # remove this line
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)
        bucket_key = (
            f"{cloud_client_upload_prefix}/.env.from-bytes."
            f"{cloud_config.aws_access_key}"
        )
        await cloud_client.upload(key=bucket_key, source=env_bytes)
        logger.info.assert_called_once_with(
            f"fastenv read the provided bytes and wrote the contents to"
            f" {cloud_config.aws_s3_bucket}/{bucket_key}"
        )

    @pytest.mark.anyio
    async def test_upload_response_from_backblaze_b2(
        self,
        cloud_config_backblaze_static: fastenv.cloud.S3Config,
        cloud_client_upload_prefix: str,
        env_bytes: bytes,
        mocker: MockerFixture,
    ) -> None:
        """Upload an object to Backblaze B2 cloud object storage, and assert that the
        upload is successful, the response contains the expected metadata, and the
        expected logger message is provided.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        cloud_client = fastenv.cloud.S3Client(config=cloud_config_backblaze_static)
        bucket_key = (
            f"{cloud_client_upload_prefix}/.env.from-bytes."
            f"{cloud_config_backblaze_static.aws_access_key}"
        )
        response = await cloud_client.upload(
            bucket_key, env_bytes, server_side_encryption="AES256"
        )
        assert response
        response_json = response.json()
        assert response_json["contentType"] == "text/plain"
        assert (
            response_json["fileInfo"]["author"]
            == cloud_config_backblaze_static.aws_access_key
        )
        assert response_json["fileName"] == bucket_key
        assert response_json["serverSideEncryption"]["algorithm"] == "AES256"
        logger.info.assert_called_once_with(
            f"fastenv read the provided bytes and wrote the contents to"
            f" {cloud_config_backblaze_static.aws_s3_bucket}/{bucket_key}"
        )

    @pytest.mark.anyio
    async def test_upload_error_incorrect_config(
        self,
        cloud_config_incorrect: fastenv.cloud.S3Config,
        env_bytes: bytes,
        mocker: MockerFixture,
    ) -> None:
        """Attempt to upload to a bucket using an incorrect configuration,
        and assert that a `RequestError` is raised with the expected status code.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        cloud_client = fastenv.cloud.S3Client(config=cloud_config_incorrect)
        with pytest.raises(fastenv.cloud.aioaws.core.RequestError) as e:
            await cloud_client.upload(key=".env.upload-error", source=env_bytes)
        assert e.value.response.status_code in {401, 403}
        assert "RequestError" in logger.error.call_args.args[0]

    @pytest.mark.anyio
    async def test_upload_error_response_from_backblaze_b2(
        self,
        cloud_config_backblaze_static: fastenv.cloud.S3Config,
        cloud_client_backblaze_b2_upload_url_response: fastenv.cloud.httpx.Response,
        env_bytes: bytes,
        mocker: MockerFixture,
    ) -> None:
        """Attempt to upload to a Backblaze B2 bucket with an invalid upload URL,
        and assert that a `RequestError` is raised with the expected status code.
        """
        mocker.patch.dict(fastenv.cloud.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.cloud, "logger", autospec=True)
        async with fastenv.cloud.httpx.AsyncClient(timeout=2) as httpx_client:
            cloud_client = fastenv.cloud.S3Client(
                http_client=httpx_client, config=cloud_config_backblaze_static
            )
            mocker.patch.object(cloud_client, "authorize_backblaze_b2_account")
            mocker.patch.object(
                cloud_client,
                "get_backblaze_b2_upload_url",
                return_value=cloud_client_backblaze_b2_upload_url_response,
            )
            with pytest.raises(fastenv.cloud.aioaws.core.RequestError) as e:
                await cloud_client.upload(key=".env.upload-error", source=env_bytes)
        assert httpx_client.is_closed
        assert e.value.response.status_code >= 400
        assert "RequestError" in logger.error.call_args.args[0]
