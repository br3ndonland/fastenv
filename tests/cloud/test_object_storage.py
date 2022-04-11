from __future__ import annotations

import freezegun
import pytest
from pytest_mock import MockerFixture

import fastenv.cloud.object_storage
import fastenv.dotenv
from tests.test_dotenv import variable_is_set


class TestObjectStorageConfig:
    """Test instantiation of `class ObjectStorageConfig`."""

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
    example_bucket_region = "us-east-1"
    example_bucket_host = (
        f"{example_bucket_name}.s3.{example_bucket_region}.amazonaws.com"
    )
    example_bucket_name_with_dots = "my.bucket.example.com"
    example_bucket_host_with_dots_in_the_bucket_name = (
        f"{example_bucket_name_with_dots}.s3.{example_bucket_region}.amazonaws.com"
    )
    example_config_kwargs_for_bucket = (
        dict(bucket_host=example_bucket_host),
        dict(bucket_name=example_bucket_name),
    )
    example_config_kwargs_for_bucket_names_with_dots = (
        dict(bucket_host=example_bucket_host_with_dots_in_the_bucket_name),
        dict(bucket_name=example_bucket_name_with_dots),
    )
    example_config_kwargs_incomplete = (
        dict(access_key=example_access_key, secret_key=example_secret_key),
        dict(access_key=example_access_key, bucket_name=example_bucket_name),
        dict(
            access_key=example_access_key,
            secret_key=example_secret_key,
            bucket_name=example_bucket_name,
        ),
    )

    def config_is_correct(
        self,
        config: fastenv.cloud.object_storage.ObjectStorageConfig,
        expected_bucket_host: str = example_bucket_host,
        expected_bucket_name: str = example_bucket_name,
        should_have_session_token: bool = False,
    ) -> bool:
        """Assert that an `ObjectStorageConfig` instance has the expected attributes."""
        if should_have_session_token:
            assert config.access_key == self.example_access_key_for_session_token
            assert config.secret_key == self.example_secret_key_for_session_token
            assert config.session_token == self.example_session_token
        else:
            assert config.access_key == self.example_access_key
            assert config.secret_key == self.example_secret_key
            assert not config.session_token
        if config.bucket_name:
            assert config.bucket_name == expected_bucket_name
        else:
            assert not config.bucket_name
        assert config.bucket_host == expected_bucket_host
        assert config.bucket_region == self.example_bucket_region
        return True

    @pytest.mark.parametrize("config_kwargs", example_config_kwargs_for_bucket)
    @pytest.mark.parametrize("should_have_session_token", (False, True))
    def test_config_from_environment_variables(
        self,
        config_kwargs: dict[str, str],
        mocker: MockerFixture,
        should_have_session_token: bool,
    ) -> None:
        """Instantiate `class ObjectStorageConfig`, allowing the class to detect the
        default AWS environment variables, and assert that the correct values are set.
        """
        environ = mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        if should_have_session_token:
            environ["AWS_ACCESS_KEY_ID"] = self.example_access_key_for_session_token
            environ["AWS_SECRET_ACCESS_KEY"] = self.example_secret_key_for_session_token
            environ["AWS_SESSION_TOKEN"] = self.example_session_token
        else:
            environ["AWS_ACCESS_KEY_ID"] = self.example_access_key
            environ["AWS_SECRET_ACCESS_KEY"] = self.example_secret_key
        environ["AWS_DEFAULT_REGION"] = self.example_bucket_region
        config = fastenv.cloud.object_storage.ObjectStorageConfig(**config_kwargs)
        assert self.config_is_correct(
            config, should_have_session_token=should_have_session_token
        )

    @pytest.mark.parametrize("config_kwargs", example_config_kwargs_for_bucket)
    @pytest.mark.parametrize("should_have_session_token", (False, True))
    def test_config_with_environment_variable_overrides(
        self,
        config_kwargs: dict[str, str],
        mocker: MockerFixture,
        should_have_session_token: bool,
    ) -> None:
        """Instantiate `class ObjectStorageConfig`, allowing the class to detect the
        default AWS environment variables, and assert that the correct values are set.

        There may be some situations, such as tests in a GitHub Actions workflow,
        in which multiple sets of credentials are present. In these situations,
        there may be environment variables such as `AWS_SESSION_TOKEN` that are set,
        but should not necessarily be used in the `ObjectStorageConfig` instance.
        Setting `session_token` to an empty string (`session_token=""`) should prevent
        `class ObjectStorageConfig` from using the environment variable value.
        """
        environ = mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        if should_have_session_token:
            environ["AWS_ACCESS_KEY_ID"] = self.example_access_key_for_session_token
            environ["AWS_SECRET_ACCESS_KEY"] = self.example_secret_key_for_session_token
            session_token = None
        else:
            environ["AWS_ACCESS_KEY_ID"] = self.example_access_key
            environ["AWS_SECRET_ACCESS_KEY"] = self.example_secret_key
            session_token = ""
        environ["AWS_SESSION_TOKEN"] = self.example_session_token
        environ["AWS_DEFAULT_REGION"] = self.example_bucket_region
        config = fastenv.cloud.object_storage.ObjectStorageConfig(
            **config_kwargs, session_token=session_token
        )
        assert self.config_is_correct(
            config, should_have_session_token=should_have_session_token
        )

    @pytest.mark.parametrize("config_kwargs", example_config_kwargs_for_bucket)
    def test_config_from_kwargs(
        self, config_kwargs: dict[str, str], mocker: MockerFixture
    ) -> None:
        """Instantiate `class ObjectStorageConfig` with keyword arguments
        and assert that the correct values are set.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key=self.example_access_key,
            secret_key=self.example_secret_key,
            bucket_region=self.example_bucket_region,
            **config_kwargs,
        )
        assert self.config_is_correct(config)

    @pytest.mark.parametrize("config_kwargs", example_config_kwargs_incomplete)
    def test_config_without_necessary_attributes(
        self, config_kwargs: dict[str, str], mocker: MockerFixture
    ) -> None:
        """Instantiate `class ObjectStorageConfig` without all necessary attributes
        and assert that an `AttributeError` is raised.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        with pytest.raises(AttributeError) as e:
            fastenv.cloud.object_storage.ObjectStorageConfig(**config_kwargs)
        assert "not provided" in str(e.value)

    @pytest.mark.parametrize(
        "config_kwargs", example_config_kwargs_for_bucket_names_with_dots
    )
    def test_config_if_bucket_name_contains_dots(
        self, config_kwargs: dict[str, str], mocker: MockerFixture
    ) -> None:
        """Assert that bucket names with dots are set correctly,
        and also correctly used to construct the bucket host.

        AWS S3 allows lowercase letters, numbers, dots (`.`), and hyphens (`-`)
        to be used in bucket names. It is common to have `.` in bucket names when
        the buckets are used for static website hosting, though AWS discourages
        use of `.` in bucket names for various technical reasons. This means that
        bucket names should not be parsed out of bucket hosts by splitting on `.`.

        This test will assert that bucket names with `.` are set correctly on
        instances of `class ObjectStorageConfig`, and that the `bucket_host` field is
        correctly constructed from the bucket name.

        https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
        https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html
        https://aws.amazon.com/blogs/aws/amazon-s3-path-deprecation-plan-the-rest-of-the-story/
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key=self.example_access_key,
            secret_key=self.example_secret_key,
            bucket_region=self.example_bucket_region,
            **config_kwargs,
        )
        assert self.config_is_correct(
            config,
            expected_bucket_host=self.example_bucket_host_with_dots_in_the_bucket_name,
            expected_bucket_name=self.example_bucket_name_with_dots,
        )

    @pytest.mark.parametrize(
        "bucket_host,bucket_region",
        (
            ("mybucket.s3.us-west-001.backblazeb2.com", "us-west-001"),
            ("mybucket.nyc3.digitaloceanspaces.com", "nyc3"),
        ),
    )
    @pytest.mark.parametrize("bucket_name", ("", None))
    def test_config_if_not_bucket_name(
        self,
        bucket_host: str,
        bucket_name: str | None,
        bucket_region: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that, if a bucket name is not provided, `bucket_name`
        is correctly parsed from `bucket_host` for supported object
        storage platforms, or is `None` for unsupported platforms.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key=self.example_access_key,
            secret_key=self.example_secret_key,
            bucket_host=bucket_host,
            bucket_name=bucket_name,
            bucket_region=bucket_region,
        )
        if "backblazeb2" in bucket_host and bucket_name is None:
            assert config.bucket_name == "mybucket"
        else:
            assert config.bucket_name is None

    def test_config_if_bucket_name_not_in_bucket_host(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that an exception is raised if `bucket_host` and `bucket_name`
        are both set, but `bucket_host` does not contain `bucket_name`.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        bucket_host = f"{self.example_bucket_name}.s3.us-west-001.backblazeb2.com"
        expected_exception_value = (
            f"Bucket host {bucket_host} does not include "
            "bucket name sigv4examplebucket."
        )
        with pytest.raises(AttributeError) as e:
            fastenv.cloud.object_storage.ObjectStorageConfig(
                access_key=self.example_access_key,
                secret_key=self.example_secret_key,
                bucket_host=bucket_host,
                bucket_name="sigv4examplebucket",
                bucket_region="us-west-001",
            )
        assert str(e.value) == expected_exception_value

    def test_config_if_bucket_region_not_in_bucket_host(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that an exception is raised if `bucket_host`
        does not contain `bucket_region`.

        Some bucket host values may omit the region name (such as AWS `us-east-1`),
        but in general the region should be present in a virtual-hosted-style URL.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        bucket_host = f"{self.example_bucket_name}.s3.us-west-001.backblazeb2.com"
        expected_exception_value = (
            f"Bucket host {bucket_host} does not include "
            f"bucket region {self.example_bucket_region}."
        )
        with pytest.raises(AttributeError) as e:
            fastenv.cloud.object_storage.ObjectStorageConfig(
                access_key=self.example_access_key,
                secret_key=self.example_secret_key,
                bucket_host=bucket_host,
                bucket_name=self.example_bucket_name,
                bucket_region=self.example_bucket_region,
            )
        assert str(e.value) == expected_exception_value


class TestObjectStorageClientUnit:
    """Test `class ObjectStorageClient` and its methods.

    This class only contains unit tests, defined as tests performed entirely within
    this project's Python code. Integration tests are added to a separate test class.
    """

    def test_client_instantiation_error(self, mocker: MockerFixture) -> None:
        """Attempt to instantiate `ObjectStorageClient` without providing a bucket,
        and assert that an `AttributeError` is raised.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        mocker.patch.object(fastenv.cloud.object_storage, "logger", autospec=True)
        with pytest.raises(AttributeError) as e:
            fastenv.cloud.object_storage.ObjectStorageClient()
        assert "not provided" in str(e.value)

    @freezegun.freeze_time("2013-05-24")
    def test_create_canonical_request_for_presigned_url_example(
        self,
        object_storage_config_for_presigned_url_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
    ) -> None:
        """Assert that canonical requests match expected output provided by AWS.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html

        The virtual-hosted-style URL in this example lacks a region. The docs mix
        path-style URLs (`s3.amazonaws.com/examplebucket`), virtual-hosted-style URLs
        without regions (`examplebucket.s3.amazonaws.com`), and virtual-hosted-style
        URLs with regions (`examplebucket.s3.us-east-1.amazonaws.com`).
        """
        object_storage_config = object_storage_config_for_presigned_url_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        expires = 86400
        now = fastenv.cloud.object_storage.datetime.datetime.now(
            tz=fastenv.cloud.object_storage.datetime.timezone.utc
        )
        x_amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        credential_scope = (
            f"{date_stamp}/{object_storage_config.bucket_region}/s3/aws4_request"
        )
        x_amz_credential = f"{object_storage_config.access_key}/{credential_scope}"
        params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": x_amz_credential,
            "X-Amz-Date": x_amz_date,
            "X-Amz-Expires": str(expires),
        }
        if object_storage_config.session_token is not None:
            params["X-Amz-Security-Token"] = object_storage_config.session_token
        params["X-Amz-SignedHeaders"] = "host"
        headers = {"host": object_storage_config.bucket_host}
        expected_beginning = (
            "GET\n"
            "/test.txt\n"
            "X-Amz-Algorithm=AWS4-HMAC-SHA256"
            "&X-Amz-Credential="
            "AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request"
            "&X-Amz-Date=20130524T000000Z"
            "&X-Amz-Expires=86400"
        )
        expected_ending = (
            "&X-Amz-SignedHeaders=host\n"
            "host:examplebucket.s3.amazonaws.com\n\n"
            "host\n"
            "UNSIGNED-PAYLOAD"
        )
        if object_storage_config.session_token is not None:
            expected_session_token = fastenv.cloud.object_storage.urllib.parse.quote(
                object_storage_config.session_token, safe=""
            )
            expected_canonical_request = (
                expected_beginning
                + f"&X-Amz-Security-Token={expected_session_token}"
                + expected_ending
            )
        else:
            expected_canonical_request = expected_beginning + expected_ending
        canonical_request = object_storage_client._create_canonical_request(
            "GET",
            "/test.txt",
            params=params,
            headers=headers,
            payload_hash="UNSIGNED-PAYLOAD",
        )
        assert canonical_request == expected_canonical_request

    @freezegun.freeze_time("2013-05-24")
    def test_create_string_to_sign_for_presigned_url_example(
        self,
        object_storage_config_for_presigned_url_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
    ) -> None:
        """Assert that strings to sign match expected output provided by AWS.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
        """
        object_storage_config = object_storage_config_for_presigned_url_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        now = fastenv.cloud.object_storage.datetime.datetime.now(
            tz=fastenv.cloud.object_storage.datetime.timezone.utc
        )
        x_amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        credential_scope = (
            f"{date_stamp}/{object_storage_config.bucket_region}/s3/aws4_request"
        )
        canonical_request = (
            "GET\n"
            "/test.txt\n"
            "X-Amz-Algorithm=AWS4-HMAC-SHA256"
            "&X-Amz-Credential="
            "AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request"
            "&X-Amz-Date=20130524T000000Z"
            "&X-Amz-Expires=86400"
            "&X-Amz-SignedHeaders=host\n"
            "host:examplebucket.s3.amazonaws.com\n\n"
            "host\n"
            "UNSIGNED-PAYLOAD"
        )
        expected_string_to_sign = (
            "AWS4-HMAC-SHA256\n"
            "20130524T000000Z\n"
            "20130524/us-east-1/s3/aws4_request\n"
            "3bfa292879f6447bbcda7001decf97f4a54dc650c8942174ae0a9121cf58ad04"
        )
        string_to_sign = object_storage_client._create_string_to_sign(
            x_amz_date=x_amz_date,
            credential_scope=credential_scope,
            canonical_request=canonical_request,
        )
        assert string_to_sign == expected_string_to_sign

    @freezegun.freeze_time("2013-05-24")
    def test_calculate_signature_for_presigned_url_example(
        self,
        object_storage_config_for_presigned_url_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
    ) -> None:
        """Assert that the calculated signature matches the expected signature
        when calculated with the provided string to sign.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
        """
        object_storage_config = object_storage_config_for_presigned_url_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        now = fastenv.cloud.object_storage.datetime.datetime.now(
            tz=fastenv.cloud.object_storage.datetime.timezone.utc
        )
        date_stamp = now.strftime("%Y%m%d")
        string_to_sign = (
            "AWS4-HMAC-SHA256\n"
            "20130524T000000Z\n"
            "20130524/us-east-1/s3/aws4_request\n"
            "3bfa292879f6447bbcda7001decf97f4a54dc650c8942174ae0a9121cf58ad04"
        )
        expected_signature = (
            "aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"
        )
        signing_key = object_storage_client._derive_signing_key(date_stamp)
        signature = object_storage_client._calculate_signature(
            signing_key, string_to_sign
        )
        assert signature == expected_signature

    @freezegun.freeze_time("2013-05-24")
    def test_generate_presigned_url_example(
        self,
        object_storage_config_for_presigned_url_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
    ) -> None:
        """Assert that presigned URLs match expected output provided by AWS.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html

        The virtual-hosted-style URL in this example lacks a region. The docs mix
        path-style URLs (`s3.amazonaws.com/examplebucket`), virtual-hosted-style URLs
        without regions (`examplebucket.s3.amazonaws.com`), and virtual-hosted-style
        URLs with regions (`examplebucket.s3.us-east-1.amazonaws.com`).

        The AWS docs do not provide a signature for the `X-Amz-Security-Token` example.
        """
        object_storage_config = object_storage_config_for_presigned_url_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        expected_x_amz_credential = fastenv.cloud.object_storage.urllib.parse.unquote(
            "AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request"
        )
        expected_x_amz_signature = (
            "aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"
            if object_storage_config.session_token is None
            else "b44654051bcc7e09ba7d82c65821043f2e091d6a5503bd053ba6c0a01b3fc216"
        )
        presigned_url = object_storage_client.generate_presigned_url(
            "GET", "test.txt", expires=86400
        )
        assert presigned_url.scheme == "https"
        assert presigned_url.host == object_storage_config.bucket_host
        assert presigned_url.path == "/test.txt"
        assert presigned_url.params["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
        assert presigned_url.params["X-Amz-Credential"] == expected_x_amz_credential
        assert presigned_url.params["X-Amz-Date"] == "20130524T000000Z"
        assert presigned_url.params["X-Amz-Expires"] == "86400"
        if object_storage_config.session_token is not None:
            presigned_url_token = presigned_url.params.get("X-Amz-Security-Token")
            assert presigned_url_token == object_storage_config.session_token
        assert presigned_url.params["X-Amz-SignedHeaders"] == "host"
        assert presigned_url.params["X-Amz-Signature"] == expected_x_amz_signature

    @pytest.mark.parametrize("expires", (0, 604900))
    def test_generate_presigned_url_expiration_time_error(self, expires: int) -> None:
        """Assert that `ValueError`s are raised for unsupported expiration times."""
        object_storage_config = fastenv.cloud.object_storage.ObjectStorageConfig(
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE",
            bucket_host="examplebucket.s3.us-east-1.amazonaws.com",
            bucket_region="us-east-1",
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        with pytest.raises(ValueError) as e:
            object_storage_client.generate_presigned_url("GET", ".env", expires=expires)
        assert "Expiration time must be between one second and one week" in str(e.value)

    @pytest.mark.parametrize("key", ("user/user1/a.png", "user/user1/${filename}"))
    @pytest.mark.parametrize("content_length", (1111, None))
    @pytest.mark.parametrize("content_type", ("image/png", None))
    @pytest.mark.parametrize("specify_content_disposition", (False, True))
    @freezegun.freeze_time("2015-12-29")
    def test_create_presigned_post_policy(
        self,
        object_storage_config_for_presigned_post_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
        key: str,
        content_length: int | None,
        content_type: str | None,
        specify_content_disposition: bool,
    ) -> None:
        """Assert that upload policies for presigned POSTs are assembled as expected.

        - Policy condition keys should be normalized to lowercase and deduplicated.
        - All expected policy conditions should be returned.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html
        """
        object_storage_config = object_storage_config_for_presigned_post_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        now = fastenv.cloud.object_storage.datetime.datetime.now(
            tz=fastenv.cloud.object_storage.datetime.timezone.utc
        )
        x_amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        expiration_time = now + fastenv.cloud.object_storage.datetime.timedelta(
            seconds=129600
        )
        expiration_time_isoformat = expiration_time.isoformat(timespec="milliseconds")
        expiration = expiration_time_isoformat.replace("+00:00", "Z")
        credential_scope = (
            f"{date_stamp}/{object_storage_config.bucket_region}/s3/aws4_request"
        )
        x_amz_credential = f"{object_storage_config.access_key}/{credential_scope}"
        required_policy_conditions = [
            {"X-Amz-Algorithm": "AWS4-HMAC-SHA256"},
            {"X-Amz-Credential": x_amz_credential},
            {"X-Amz-Date": x_amz_date},
        ]
        expected_required_policy_conditions = [
            {"x-amz-algorithm": "AWS4-HMAC-SHA256"},
            {
                "x-amz-credential": (
                    "AKIAIOSFODNN7EXAMPLE/20151229/us-east-1/s3/aws4_request"
                )
            },
            {"x-amz-date": "20151229T000000Z"},
        ]
        if object_storage_config.session_token:
            required_policy_conditions.append(
                {"X-Amz-Security-Token": object_storage_config.session_token}
            )
            expected_required_policy_conditions.append(
                {"x-amz-security-token": object_storage_config.session_token}
            )
        optional_policy_conditions: list = [
            {"acl": "public-read"},
            {"bucket": "sigv4examplebucket"},
            ["starts-with", "$Content-Type", "image/"],
            ["starts-with", "$x-amz-meta-tag", ""],
            {
                "success_action_redirect": (
                    "http://sigv4examplebucket.s3.amazonaws.com/successful_upload.html"
                )
            },
            {"x-amz-meta-uuid": "14365123651274"},
            {"x-amz-server-side-encryption": "AES256"},
        ]
        expected_optional_policy_conditions = list(optional_policy_conditions)
        if key:
            if key == "user/user1/a.png":
                expected_optional_policy_conditions.append({"key": key})
                if specify_content_disposition:
                    expected_optional_policy_conditions.append(
                        {"content-disposition": 'attachment; filename="a.png"'}
                    )
            if "${filename}" in key:
                expected_optional_policy_conditions.append(
                    ["starts-with", "$key", "user/user1/"]
                )
        if content_length:
            expected_optional_policy_conditions.append(
                ["content-length-range", content_length, content_length]
            )
        if content_type:
            expected_optional_policy_conditions.append({"content-type": content_type})
        expected_policy = {
            "expiration": "2015-12-30T12:00:00.000Z",
            "conditions": (
                expected_required_policy_conditions
                + expected_optional_policy_conditions
            ),
        }
        policy = object_storage_client._create_presigned_post_policy(
            expiration,
            required_policy_conditions,
            key,
            content_length=content_length,
            content_type=content_type,
            server_side_encryption="AES256",
            specify_content_disposition=specify_content_disposition,
            additional_policy_conditions=optional_policy_conditions,
        )
        assert policy["expiration"] == expiration == "2015-12-30T12:00:00.000Z"
        assert len(policy["conditions"]) == len(expected_policy["conditions"])
        for expected_policy_condition in expected_policy["conditions"]:
            assert expected_policy_condition in policy["conditions"]

    @freezegun.freeze_time("2015-12-29")
    def test_calculate_signature_for_presigned_post_example(
        self,
        object_storage_config_for_presigned_post_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
    ) -> None:
        """Assert that the signature calculated using the provided string to sign
        matches the expected signature. For presigned POSTs, the string to sign
        is created by UTF-8-encoding an upload policy and converting to Base64.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html
        """
        object_storage_config = object_storage_config_for_presigned_post_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        now = fastenv.cloud.object_storage.datetime.datetime.now(
            tz=fastenv.cloud.object_storage.datetime.timezone.utc
        )
        date_stamp = now.strftime("%Y%m%d")
        base64_encoded_policy = (
            "eyAiZXhwaXJhdGlvbiI6ICIyMDE1LTEyLTMwVDEyOjAwOjAwLjAwMFoiLA0KICAiY29uZGl0"
            "aW9ucyI6IFsNCiAgICB7ImJ1Y2tldCI6ICJzaWd2NGV4YW1wbGVidWNrZXQifSwNCiAgICBb"
            "InN0YXJ0cy13aXRoIiwgIiRrZXkiLCAidXNlci91c2VyMS8iXSwNCiAgICB7ImFjbCI6ICJw"
            "dWJsaWMtcmVhZCJ9LA0KICAgIHsic3VjY2Vzc19hY3Rpb25fcmVkaXJlY3QiOiAiaHR0cDov"
            "L3NpZ3Y0ZXhhbXBsZWJ1Y2tldC5zMy5hbWF6b25hd3MuY29tL3N1Y2Nlc3NmdWxfdXBsb2Fk"
            "Lmh0bWwifSwNCiAgICBbInN0YXJ0cy13aXRoIiwgIiRDb250ZW50LVR5cGUiLCAiaW1hZ2Uv"
            "Il0sDQogICAgeyJ4LWFtei1tZXRhLXV1aWQiOiAiMTQzNjUxMjM2NTEyNzQifSwNCiAgICB7"
            "IngtYW16LXNlcnZlci1zaWRlLWVuY3J5cHRpb24iOiAiQUVTMjU2In0sDQogICAgWyJzdGFy"
            "dHMtd2l0aCIsICIkeC1hbXotbWV0YS10YWciLCAiIl0sDQoNCiAgICB7IngtYW16LWNyZWRl"
            "bnRpYWwiOiAiQUtJQUlPU0ZPRE5ON0VYQU1QTEUvMjAxNTEyMjkvdXMtZWFzdC0xL3MzL2F3"
            "czRfcmVxdWVzdCJ9LA0KICAgIHsieC1hbXotYWxnb3JpdGhtIjogIkFXUzQtSE1BQy1TSEEy"
            "NTYifSwNCiAgICB7IngtYW16LWRhdGUiOiAiMjAxNTEyMjlUMDAwMDAwWiIgfQ0KICBdDQp9"
        )
        string_to_sign = base64_encoded_policy
        expected_signature = (
            "8afdbf4008c03f22c2cd3cdb72e4afbb1f6a588f3255ac628749a66d7f09699e"
        )
        signing_key = object_storage_client._derive_signing_key(date_stamp)
        signature = object_storage_client._calculate_signature(
            signing_key, string_to_sign
        )
        assert signature == expected_signature

    @pytest.mark.parametrize(
        "additional_form_data",
        ({"x-amz-meta-tag": ""}, {"Content-Type": "image/png"}),
    )
    @freezegun.freeze_time("2015-12-29")
    def test_prepare_presigned_post_form_data(
        self,
        object_storage_config_for_presigned_post_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
        object_storage_client_upload_policy_from_presigned_post_example: dict[
            fastenv.cloud.object_storage.Literal["expiration", "conditions"],
            str | dict[str, str] | list,
        ],
        additional_form_data: dict[str, str] | None,
    ) -> None:
        """Assert that form data for presigned POSTs are assembled as expected.

        "key" is a required form data field, though the docs are not clear on this.
        "key" is not always included in policies directly. For example, an upload
        policy may need to allow the user to supply a filename. In this case, the
        filename is not known ahead of time, so an exact "key" condition cannot be
        set. Other forms of condition matching such as "starts-with" can be used,
        and the form data should supply a template field like `${filename}`.
        This test will assert that the "key" field in the form data is correcly
        populated from the "starts-with" condition in the example in the docs.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html
        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html
        """
        object_storage_config = object_storage_config_for_presigned_post_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        policy = object_storage_client_upload_policy_from_presigned_post_example
        expected_additional_form_data = (
            {key.casefold(): value for key, value in additional_form_data.items()}
            if additional_form_data
            else None
        )
        expected_form_data = {
            "acl": "public-read",
            "key": "user/user1/${filename}",
            "success_action_redirect": (
                "http://sigv4examplebucket.s3.amazonaws.com/successful_upload.html"
            ),
            "x-amz-algorithm": "AWS4-HMAC-SHA256",
            "x-amz-credential": (
                "AKIAIOSFODNN7EXAMPLE/20151229/us-east-1/s3/aws4_request"
            ),
            "x-amz-date": "20151229T000000Z",
            "x-amz-meta-uuid": "14365123651274",
            "x-amz-server-side-encryption": "AES256",
        }
        form_data = object_storage_client._prepare_presigned_post_form_data(
            policy, additional_form_data
        )
        if expected_additional_form_data:
            assert form_data == {**expected_form_data, **expected_additional_form_data}
        else:
            assert form_data == expected_form_data

    @freezegun.freeze_time("2015-12-29")
    def test_prepare_presigned_post_form_data_key_field_error(
        self,
        object_storage_config_for_presigned_post_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
        object_storage_client_upload_policy_from_presigned_post_example: dict[
            fastenv.cloud.object_storage.Literal["expiration", "conditions"],
            str | dict[str, str] | list,
        ],
    ) -> None:
        """Assert that a missing or incorrectly-typed "key" field
        in presigned POST form data raises a `KeyError`.

        "key" is a required form data field (the dict key is literally "key"),
        though the docs are not clear on this requirement.

        This test will assert that missing or incorrectly-typed "key" fields
        raise `KeyError`s with appropriate error messages.
        """
        object_storage_config = object_storage_config_for_presigned_post_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        policy = object_storage_client_upload_policy_from_presigned_post_example
        assert isinstance(policy["conditions"], list)
        policy["conditions"].remove(["starts-with", "$key", "user/user1/"])
        with pytest.raises(KeyError) as e_missing:
            object_storage_client._prepare_presigned_post_form_data(policy)
        with pytest.raises(KeyError) as e_mistyped:
            policy["conditions"].insert(0, {"key": True})
            object_storage_client._prepare_presigned_post_form_data(policy)
        assert "Missing required form data key" in str(e_missing.value)
        assert "Incorrect data type" in str(e_mistyped.value)

    @freezegun.freeze_time("2015-12-29")
    def test_prepare_presigned_post_form_data_unsupported_field_error(
        self,
        object_storage_config_for_presigned_post_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
        object_storage_client_upload_policy_from_presigned_post_example: dict[
            fastenv.cloud.object_storage.Literal["expiration", "conditions"],
            str | dict[str, str] | list,
        ],
    ) -> None:
        """Assert that attempting to add unsupported form data fields
        to a presigned POST raises a `KeyError`.
        """
        object_storage_config = object_storage_config_for_presigned_post_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        policy = object_storage_client_upload_policy_from_presigned_post_example
        with pytest.raises(KeyError) as e:
            object_storage_client._prepare_presigned_post_form_data(
                policy, {"foobar": "baz"}
            )
        assert "Unsupported form data key: foobar" in str(e.value)

    @freezegun.freeze_time("2015-12-29")
    def test_generate_presigned_post_example(
        self,
        object_storage_config_for_presigned_post_example: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
        object_storage_client_upload_policy_from_presigned_post_example: dict[
            fastenv.cloud.object_storage.Literal["expiration", "conditions"],
            str | dict[str, str] | list,
        ],
    ) -> None:
        """Assert that presigned POSTs match expected output provided by AWS.

        https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-post-example.html
        """
        object_storage_config = object_storage_config_for_presigned_post_example
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            config=object_storage_config
        )
        additional_policy_conditions = list(
            object_storage_client_upload_policy_from_presigned_post_example[
                "conditions"
            ]
        )
        expected_signature = (
            "10e5594f81e5777e9472e582328a6292cc06e28e019ff2134eacdfdc1a545450"
            if object_storage_client._config.session_token
            else "93d9d2b12aa036679999b667a4e5a87f158db7b2bd8df23cf8e95e49caa44cd5"
        )
        # docs: "8afdbf4008c03f22c2cd3cdb72e4afbb1f6a588f3255ac628749a66d7f09699e"
        url, data = object_storage_client.generate_presigned_post(
            bucket_path="/",
            content_length=None,
            content_type="image/jpeg",
            expires=129600,
            server_side_encryption="AES256",
            specify_content_disposition=False,
            additional_policy_conditions=additional_policy_conditions,
        )
        assert str(url) == "https://sigv4examplebucket.s3.amazonaws.com/"
        # required policy conditions
        assert data["policy"]
        assert data["key"] == "user/user1/${filename}"
        assert data["x-amz-algorithm"] == "AWS4-HMAC-SHA256"
        assert data["x-amz-credential"] == (
            "AKIAIOSFODNN7EXAMPLE/20151229/us-east-1/s3/aws4_request"
        )
        assert data["x-amz-date"] == "20151229T000000Z"
        if object_storage_client._config.session_token:
            assert (
                data["x-amz-security-token"]
                == object_storage_client._config.session_token
            )
        assert data["x-amz-signature"] == expected_signature
        # optional policy conditions
        assert data["acl"] == "public-read"
        assert data["content-type"] == "image/jpeg"
        assert data["success_action_redirect"] == (
            "http://sigv4examplebucket.s3.amazonaws.com/successful_upload.html"
        )
        assert data["x-amz-meta-uuid"] == "14365123651274"
        assert data["x-amz-server-side-encryption"] == "AES256"


class TestObjectStorageClientIntegration:
    """Test `class ObjectStorageClient` and its methods.

    This class contains integration tests, defined as tests that require resources
    outside this project's Python code (object storage buckets, for example).

    The HTTPX client instances have extended timeouts and support for retries.
    This can help account for network issues.
    """

    key = ".env.testing"

    @pytest.mark.anyio
    async def test_download_to_file_with_object_storage_config(
        self,
        object_storage_config: fastenv.cloud.object_storage.ObjectStorageConfig,
        env_file: fastenv.cloud.object_storage.anyio.Path,
        env_file_object_expected_output: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Download a file from cloud object storage with an `ObjectStorageConfig`
        instance, load the file, and assert all expected variables are set.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        environ = mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config
        )
        destination = env_file.parent / f".env.{object_storage_config.access_key}"
        env_file_download = await object_storage_client.download(self.key, destination)
        dotenv = await fastenv.dotenv.load_dotenv(env_file_download)
        assert dotenv.source == env_file_download
        for expected_key, expected_value in env_file_object_expected_output.items():
            assert variable_is_set(dotenv, environ, expected_key, expected_value)
        logger.info.assert_called_once_with(
            f"fastenv loaded {self.key} from {object_storage_config.bucket_host} "
            f"and wrote the contents to {destination}"
        )

    @pytest.mark.anyio
    async def test_download_to_string_with_object_storage_config(
        self,
        object_storage_config: fastenv.cloud.object_storage.ObjectStorageConfig,
        env_file_object_expected_output: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Download a file from cloud object storage with an `ObjectStorageConfig`
        instance, load the file, and assert all expected variables are set.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        environ = mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config
        )
        env_file_contents = await object_storage_client.download(self.key)
        assert isinstance(env_file_contents, str)
        dotenv = fastenv.dotenv.DotEnv(env_file_contents)
        for expected_key, expected_value in env_file_object_expected_output.items():
            assert variable_is_set(dotenv, environ, expected_key, expected_value)
        logger.info.assert_called_once_with(
            f"fastenv loaded {self.key} from {object_storage_config.bucket_host}"
        )

    @pytest.mark.anyio
    async def test_download_error(
        self,
        object_storage_config: fastenv.cloud.object_storage.ObjectStorageConfig,
        mocker: MockerFixture,
    ) -> None:
        """Attempt to download a non-existent file from cloud object storage,
        and assert that an `HTTPStatusError` is raised with the expected status code.

        This test sometimes suffers from connection resets and timeouts.
        To prevent this test from being flaky, `httpx.ReadError` is allowed.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config
        )
        expected_exceptions: tuple = (
            fastenv.cloud.object_storage.httpx.HTTPStatusError,
            fastenv.cloud.object_storage.httpx.ReadError,
        )
        with pytest.raises(expected_exceptions) as e:
            await object_storage_client.download(
                bucket_path=f"{self.key}-does-not-exist"
            )
        if e.type is fastenv.cloud.object_storage.httpx.HTTPStatusError:
            assert e.value.response.status_code == 404
            assert str(object_storage_config.bucket_name) in str(e.value)
            assert "fastenv error" in logger.error.call_args.args[0]
            assert "HTTPStatusError" in logger.error.call_args.args[0]

    @pytest.mark.anyio
    @pytest.mark.parametrize("server_side_encryption", (None, "AES256"))
    async def test_upload_from_file_with_object_storage_config(
        self,
        object_storage_config: fastenv.cloud.object_storage.ObjectStorageConfig,
        object_storage_client_upload_prefix: str,
        env_file: fastenv.cloud.object_storage.anyio.Path,
        mocker: MockerFixture,
        server_side_encryption: fastenv.cloud.object_storage.Literal["AES256", None],
    ) -> None:
        """Upload a file to cloud object storage, and assert that the
        expected logger message is provided after a successful upload.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config
        )
        bucket_path = (
            f"{object_storage_client_upload_prefix}/.env.from-file."
            f"{object_storage_config.access_key}"
        )
        await object_storage_client.upload(
            bucket_path=bucket_path,
            source=env_file,
            server_side_encryption=server_side_encryption,
        )
        logger.info.assert_called_once_with(
            f"fastenv loaded {env_file} and wrote the contents to"
            f" {object_storage_config.bucket_host}/{bucket_path}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("server_side_encryption", (None, "AES256"))
    async def test_upload_from_string_with_object_storage_config(
        self,
        object_storage_config: fastenv.cloud.object_storage.ObjectStorageConfig,
        object_storage_client_upload_prefix: str,
        env_str: str,
        mocker: MockerFixture,
        server_side_encryption: fastenv.cloud.object_storage.Literal["AES256", None],
    ) -> None:
        """Upload a string to cloud object storage, and assert that the
        expected logger message is provided after a successful upload.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config
        )
        bucket_path = (
            f"{object_storage_client_upload_prefix}/.env.from-string."
            f"{object_storage_config.access_key}"
        )
        await object_storage_client.upload(
            bucket_path=bucket_path,
            source=env_str,
            server_side_encryption=server_side_encryption,
        )
        logger.info.assert_called_once_with(
            f"fastenv loaded the provided string and wrote the contents to"
            f" {object_storage_config.bucket_host}/{bucket_path}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("server_side_encryption", (None, "AES256"))
    async def test_upload_from_bytes_with_object_storage_config(
        self,
        object_storage_config: fastenv.cloud.object_storage.ObjectStorageConfig,
        object_storage_client_upload_prefix: str,
        env_bytes: bytes,
        mocker: MockerFixture,
        server_side_encryption: fastenv.cloud.object_storage.Literal["AES256", None],
    ) -> None:
        """Upload bytes to cloud object storage, and assert that the
        expected logger message is provided after a successful upload.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config
        )
        bucket_path = (
            f"{object_storage_client_upload_prefix}/.env.from-bytes."
            f"{object_storage_config.access_key}"
        )
        await object_storage_client.upload(
            bucket_path=bucket_path,
            source=env_bytes,
            server_side_encryption=server_side_encryption,
        )
        logger.info.assert_called_once_with(
            f"fastenv read the provided bytes and wrote the contents to"
            f" {object_storage_config.bucket_host}/{bucket_path}"
        )

    @pytest.mark.anyio
    async def test_upload_response_from_backblaze_b2(
        self,
        object_storage_config_backblaze_static: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
        object_storage_client_upload_prefix: str,
        env_bytes: bytes,
        mocker: MockerFixture,
    ) -> None:
        """Upload an object to Backblaze B2 cloud object storage, and assert that the
        upload is successful, the response contains the expected metadata, and the
        expected logger message is provided.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config_backblaze_static
        )
        bucket_path = (
            f"{object_storage_client_upload_prefix}/.env.from-bytes."
            f"{object_storage_config_backblaze_static.access_key}"
        )
        response = await object_storage_client.upload(
            bucket_path, env_bytes, server_side_encryption="AES256"
        )
        assert response
        response_json = response.json()
        assert response_json["contentType"] == "text/plain"
        assert (
            response_json["fileInfo"]["author"]
            == object_storage_config_backblaze_static.access_key
        )
        assert response_json["fileName"] == bucket_path
        assert response_json["serverSideEncryption"]["algorithm"] == "AES256"
        logger.info.assert_called_once_with(
            f"fastenv read the provided bytes and wrote the contents to"
            f" {object_storage_config_backblaze_static.bucket_host}/{bucket_path}"
        )

    @pytest.mark.anyio
    async def test_upload_error_incorrect_config(
        self,
        object_storage_config_incorrect: (
            fastenv.cloud.object_storage.ObjectStorageConfig
        ),
        env_bytes: bytes,
        mocker: MockerFixture,
    ) -> None:
        """Attempt to upload to a bucket using an incorrect configuration,
        and assert that an `HTTPStatusError` is raised with the expected status code.

        This test sometimes suffers from connection resets and timeouts.
        To prevent this test from being flaky, `httpx.ReadError` is allowed.
        """
        mocker.patch.dict(fastenv.cloud.object_storage.os.environ, clear=True)
        logger = mocker.patch.object(
            fastenv.cloud.object_storage, "logger", autospec=True
        )
        transport = fastenv.cloud.object_storage.httpx.AsyncHTTPTransport(retries=5)
        httpx_client = fastenv.cloud.object_storage.httpx.AsyncClient(
            timeout=30, transport=transport
        )
        object_storage_client = fastenv.cloud.object_storage.ObjectStorageClient(
            client=httpx_client, config=object_storage_config_incorrect
        )
        expected_exceptions: tuple = (
            fastenv.cloud.object_storage.httpx.HTTPStatusError,
            fastenv.cloud.object_storage.httpx.ReadError,
        )
        with pytest.raises(expected_exceptions) as e:
            await object_storage_client.upload(
                bucket_path=".env.upload-error", source=env_bytes
            )
        if e.type is fastenv.cloud.object_storage.httpx.HTTPStatusError:
            assert e.value.response.status_code in {401, 403}
            assert "HTTPStatusError" in logger.error.call_args.args[0]
