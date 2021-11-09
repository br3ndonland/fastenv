from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

import fastenv.dotenv

dotenv_args: tuple[tuple[str, str, str], ...] = (
    (
        "AWS_ACCESS_KEY_ID_EXAMPLE=AKIAIOSFODNN7EXAMPLE\n",
        "AWS_ACCESS_KEY_ID_EXAMPLE",
        "AKIAIOSFODNN7EXAMPLE",
    ),
    (
        "AWS_SECRET_ACCESS_KEY_EXAMPLE=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE\n",
        "AWS_SECRET_ACCESS_KEY_EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE",
    ),
    (
        "CSV_VARIABLE=comma,separated,value\n",
        "CSV_VARIABLE",
        "comma,separated,value",
    ),
    (
        "EMPTY_VARIABLE= \n",
        "EMPTY_VARIABLE",
        "",
    ),
    (
        "INLINE_COMMENT=no_comment  # inline comment  \n",
        "INLINE_COMMENT",
        "no_comment",
    ),
    (
        'JSON_EXAMPLE=\'{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}\'',
        "JSON_EXAMPLE",
        '{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}',
    ),
    (
        "PASSWORD='64w2Q$!&,,[EXAMPLE'\n",
        "PASSWORD",
        "64w2Q$!&,,[EXAMPLE",
    ),
    (
        "QUOTES_AND_WHITESPACE=\"' text and spaces '\"\n",
        "QUOTES_AND_WHITESPACE",
        "text and spaces",
    ),
    (
        "URI_TO_DIRECTORY=~/dev",
        "URI_TO_DIRECTORY",
        "~/dev",
    ),
    (
        "URI_TO_S3_BUCKET=s3://mybucket/.env\n",
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

input_args: tuple[str, ...] = tuple(arg[0] for arg in dotenv_args)

input_kwargs: dict[str, str] = {arg[1]: arg[2] for arg in dotenv_args}

dotenv_args_with_incorrect_types: tuple = ({"key": "value"}, 123, [1, 2, 3])

dotenv_kwargs_with_incorrect_types: tuple[tuple[dict, str, str], ...] = (
    ({"dict": {"key": "value"}}, "DICT", "{'key': 'value'}"),
    ({"int": 123}, "INT", "123"),
    ({"list": [1, 2, 3]}, "LIST", "[1, 2, 3]"),
)

dotenv_files_output: tuple[tuple[str, str], ...] = (
    ("AWS_ACCESS_KEY_ID_EXAMPLE", "AKIAIOSMULTI2EXAMPLE"),
    ("AWS_SECRET_ACCESS_KEY_EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPMULTI2EXAMPLE"),
    ("CSV_VARIABLE", "multi,2,example"),
    ("MULTI_0_VARIABLE", "multi_0_value"),
    ("MULTI_1_VARIABLE", "multi_1_value"),
    ("MULTI_2_VARIABLE", "multi_2_value"),
)


def variable_is_set(
    dotenv: fastenv.dotenv.DotEnv,
    environ: fastenv.dotenv.MutableMapping,
    expected_key: str,
    expected_value: str,
) -> bool:
    """Assert that a `DotEnv` instance has the expected keys and values."""
    assert isinstance(dotenv, fastenv.dotenv.DotEnv)
    assert dotenv(expected_key) == expected_value
    assert dotenv[expected_key] == expected_value
    assert dotenv.getenv(expected_key) == expected_value
    assert environ[expected_key] == expected_value
    assert environ.get(expected_key) == expected_value
    assert fastenv.dotenv.os.getenv(expected_key) == expected_value
    return True


def variable_is_unset(
    dotenv: fastenv.dotenv.DotEnv,
    environ: fastenv.dotenv.MutableMapping,
    unset_key: str,
) -> bool:
    """Assert that a `DotEnv` instance has unset the given variable."""
    assert isinstance(dotenv, fastenv.dotenv.DotEnv)
    assert dotenv.get(unset_key) is None
    assert dotenv.getenv(unset_key, "not_set") == "not_set"
    assert environ.get(unset_key) is None
    with pytest.raises(KeyError):
        dotenv[unset_key]
    return True


def response_is_correct(
    dotenv: fastenv.dotenv.DotEnv,
    response: dict | str | None,
    expected_key: str,
    expected_value: str,
) -> bool:
    """Assert that a `DotEnv` instance responds to a call with the expected dict."""
    assert isinstance(response, dict)
    assert response[expected_key] == expected_value
    assert response == dict(dotenv)
    assert len(response) == len(dotenv)
    return True


class TestDotEnvClass:
    """Test `class DotEnv` and its methods."""

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_instantiate_dotenv_class_with_arg(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with a `"key=value"` string argument and
        assert that it is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(input_arg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == 1

    @pytest.mark.parametrize("input_arg", dotenv_args_with_incorrect_types)
    def test_instantiate_dotenv_class_with_arg_incorrect_type(
        self, input_arg: dict | int | list, mocker: MockerFixture
    ) -> None:
        """Assert that attempting to instantiate `class DotEnv`
        with any non-string arguments raises a `TypeError`.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        with pytest.raises(TypeError) as e:
            fastenv.dotenv.DotEnv(input_arg)  # type: ignore[arg-type]
        assert "Arguments passed to DotEnv instances should be strings" in str(e.value)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_instantiate_dotenv_class_with_args(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with `"key=value"` string arguments and
        assert that each is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(*input_args)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_instantiate_dotenv_class_with_kwarg(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with a `key=value` keyword argument ("kwarg")
        and assert that it is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**{output_key: output_value})
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == 1

    @pytest.mark.parametrize(
        "input_kwarg, output_key, output_value", dotenv_kwargs_with_incorrect_types
    )
    def test_instantiate_dotenv_class_with_kwarg_incorrect_type(
        self,
        input_kwarg: dict,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that attempting to instantiate `class DotEnv` with a non-string kwarg
        converts the value to a string, sets the variable in both the `DotEnv` instance
        and `os.environ`, and returns a dict of the key and corresponding value set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwarg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == 1

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_instantiate_dotenv_class_with_kwargs(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with `key=value` keyword arguments ("kwargs")
        and assert that each is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_instantiate_dotenv_class_with_both_args_and_kwargs(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with a combination of args and kwargs,
        assert that each is set in both `os.environ` and the `DotEnv` instance,
        and verify left-to-right mapping insertion order (kwargs override args).
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(
            "AWS_ACCESS_KEY_ID_EXAMPLE=OVERRIDETHIS1EXAMPLE",
            *input_args,
            **input_kwargs,
        )
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_instantiate_dotenv_class_with_string(
        self,
        env_str: str,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with a multi-variable string argument and assert
        that each variable is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(env_str)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)

    def test_get_single_variable_unset(self, mocker: MockerFixture) -> None:
        """Assert that attempting to get an unset variable returns `None` from a call,
        and raises a `KeyError` when square bracket syntax is used.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        assert dotenv("unset") is None
        assert dotenv.get("unset") is None
        assert dotenv.getenv("unset") is None
        assert dotenv.getenv("unset", "not_set") == "not_set"
        with pytest.raises(KeyError):
            dotenv["unset"]

    def test_get_variables(self, mocker: MockerFixture) -> None:
        """Assert that calling a `DotEnv` instance with variable keys
        returns a dict containing the keys and corresponding values.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        assert dotenv(*input_kwargs.keys()) == input_kwargs
        for key, value in input_kwargs.items():
            assert dotenv.get(key) == value

    def test_get_and_set_variables_in_single_call(self, mocker: MockerFixture) -> None:
        """Assert that calling a `DotEnv` instance with a combination of variables
        to get and set returns a dict containing the keys and corresponding values.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        expected_result = {**input_kwargs, "KEY4": "value4"}
        dotenv = fastenv.dotenv.DotEnv("KEY4=value4")
        assert dotenv("KEY4", **input_kwargs) == expected_result
        for key, value in expected_result.items():
            assert dotenv.get(key) == value

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_set_variable_with_call(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting a single variable with a call to a `DotEnv` instance
        sets the variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the key and corresponding value that were set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(input_arg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    @pytest.mark.parametrize("input_arg", dotenv_args_with_incorrect_types)
    def test_set_variable_with_call_and_incorrect_type(
        self, input_arg: dict | int | list, mocker: MockerFixture
    ) -> None:
        """Assert that attempting to call a `DotEnv` instance
        with any non-string arguments raises a `TypeError`.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        with pytest.raises(TypeError) as e:
            dotenv("KEY=value", input_arg)  # type: ignore[arg-type]
        assert not len(dotenv)
        assert "Arguments passed to DotEnv instances should be strings" in str(e.value)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_set_variable_with_square_brackets(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting a single variable with square brackets
        sets the variable in both the `DotEnv` instance and `os.environ`.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        dotenv[output_key] = output_value
        assert variable_is_set(dotenv, environ, output_key, output_value)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_set_variables_with_call_and_args(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(*input_args)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_set_variables_with_call_and_kwargs(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(**input_kwargs)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_set_variables_with_call_and_both_args_and_kwargs(
        self,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(
            "AWS_ACCESS_KEY_ID_EXAMPLE=OVERRIDETHIS1EXAMPLE",
            *input_args,
            **input_kwargs,
        )
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    @pytest.mark.parametrize(
        "input_kwarg, output_key, output_value", dotenv_kwargs_with_incorrect_types
    )
    def test_set_variables_with_call_and_kwarg_incorrect_type(
        self,
        input_kwarg: dict,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that attempting to set a variable with a non-string kwarg converts
        the value to a string, sets the variable in both the `DotEnv` instance and
        `os.environ`, and returns a dict of the key and corresponding value set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(**input_kwarg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    def test_set_variables_with_call_and_string(
        self,
        env_str: str,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(env_str)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    @pytest.mark.parametrize("comment", ("#no_spaces", "  #  spaces", "# key=value"))
    def test_set_variables_with_call_and_string_comments(
        self, comment: str, mocker: MockerFixture
    ) -> None:
        """Assert that comments are ignored when calling a `DotEnv` instance."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        dotenv(comment)
        assert dotenv(comment) is None
        with pytest.raises(KeyError):
            dotenv[comment]
        assert len(dotenv) == 0

    def test_delete_variable(self, mocker: MockerFixture) -> None:
        """Assert that deleting a variable from a `DotEnv` instance deletes the
        corresponding variable from both the `DotEnv` instance and `os.environ`.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        for key in input_kwargs:
            del dotenv[key]
            assert variable_is_unset(dotenv, environ, key)
        assert len(dotenv) == 0

    def test_delete_variables(self, mocker: MockerFixture) -> None:
        """Assert that deleting variables from a `DotEnv` instance deletes the
        corresponding variables from both the `DotEnv` instance and `os.environ`.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        dotenv.delenv(*input_kwargs.keys())
        for key in input_kwargs:
            assert variable_is_unset(dotenv, environ, key)
        assert len(dotenv) == 0

    def test_delete_variables_skip_unset(self, mocker: MockerFixture) -> None:
        """Assert that unset variables are skipped when deleting `DotEnv` variables."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv_delete_item = mocker.patch.object(
            fastenv.dotenv.DotEnv, "__delitem__", autospec=True
        )
        dotenv = fastenv.dotenv.DotEnv("EXAMPLE_KEY=example_value UNSET")
        assert dotenv.getenv("EXAMPLE_KEY")
        assert not (dotenv.getenv("UNSET") and fastenv.dotenv.os.getenv("UNSET"))
        dotenv.delenv("EXAMPLE_KEY", "UNSET")
        dotenv_delete_item.assert_called_once()
        assert "EXAMPLE_KEY" in dotenv_delete_item.call_args.args
        assert "UNSET" not in dotenv_delete_item.call_args.args

    def test_iter(self, mocker: MockerFixture) -> None:
        """Assert that calling the `__iter__` method on a
        `DotEnv` instance appropriately iterates over its keys.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        dotenv_iterator = iter(dotenv)
        assert list(dotenv) == list(input_kwargs.keys())
        for _ in input_kwargs:
            iteration_result = next(dotenv_iterator)
            assert iteration_result in input_kwargs
            assert isinstance(iteration_result, str)
        with pytest.raises(StopIteration):
            next(dotenv_iterator)

    def test_dict(self, mocker: MockerFixture) -> None:
        """Assert that a `DotEnv` instance serializes into a dictionary as expected."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        assert dict(dotenv) == input_kwargs


class TestDotEnvMethods:
    """Test methods associated with `class DotEnv`."""

    @pytest.mark.anyio
    async def test_find_dotenv_with_resolved_path_to_file(
        self, env_file: fastenv.dotenv.anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `find_dotenv` with a resolved filepath
        returns the path straight away without further iteration.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        iterdir = mocker.patch.object(fastenv.dotenv.anyio.Path, "iterdir")
        resolved_path = await env_file.resolve()
        result = await fastenv.dotenv.find_dotenv(resolved_path)
        assert result == resolved_path
        iterdir.assert_not_called()

    @pytest.mark.anyio
    async def test_find_dotenv_with_file_in_same_dir(
        self, env_file: fastenv.dotenv.anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `find_dotenv` with the name of a dotenv file in the
        same directory returns the path straight away without further iteration.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        iterdir = mocker.patch.object(fastenv.dotenv.anyio.Path, "iterdir")
        resolved_path = await env_file.resolve()
        fastenv.dotenv.os.chdir(env_file.parent)
        result = await fastenv.dotenv.find_dotenv(env_file.name)
        assert result == resolved_path
        iterdir.assert_not_called()

    @pytest.mark.anyio
    async def test_find_dotenv_with_file_from_sub_dir(
        self,
        env_file: fastenv.dotenv.anyio.Path,
        env_file_child_dir: fastenv.dotenv.anyio.Path,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `find_dotenv` from a sub-directory, with the name of
        a dotenv file in a directory above, returns the path to the dotenv file.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        resolved_path = await env_file.resolve()
        fastenv.dotenv.os.chdir(env_file_child_dir)
        result = await fastenv.dotenv.find_dotenv(env_file.name)
        assert result == resolved_path

    @pytest.mark.anyio
    async def test_find_dotenv_no_file_with_raise(self, mocker: MockerFixture) -> None:
        """Assert that calling `find_dotenv` when the dotenv file cannot be found
        raises a `FileNotFoundError` with the filename included in the exception.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.find_dotenv(".env.nofile")
        assert ".env.nofile" in str(e.value)

    @pytest.mark.anyio
    async def test_load_dotenv_no_file_with_raise(self, mocker: MockerFixture) -> None:
        """Assert that calling `load_dotenv` with `find_source=True` and the
        name of a source file that does not exist raises `FileNotFoundError`.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.load_dotenv(".env.nofile", find_source=True)
        assert ".env.nofile" in str(e.value)
        logger.error.assert_called_once_with(
            "fastenv error: FileNotFoundError Could not find .env.nofile"
        )

    @pytest.mark.anyio
    async def test_load_dotenv_no_file_no_raise(self, mocker: MockerFixture) -> None:
        """Assert that calling `load_dotenv` with `find_source=True`,
        `raise_exceptions=False`, and the name of a source file that
        does not exist returns an empty `DotEnv` instance.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(
            ".env.nofile", find_source=True, raise_exceptions=False
        )
        assert len(dotenv) == 0
        logger.error.assert_called_once_with(
            "fastenv error: FileNotFoundError Could not find .env.nofile"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    async def test_load_dotenv_file(
        self,
        env_file: fastenv.dotenv.anyio.Path,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with a correct path to a dotenv file
        returns a `DotEnv` instance with all expected variables set.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(env_file)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)
        assert dotenv.source == env_file
        logger.info.assert_called_once_with(
            f"fastenv loaded {len(dotenv_args)} variables from {env_file}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("sort_dotenv", (False, True))
    async def test_load_dotenv_sorted(
        self,
        env_file_unsorted: fastenv.dotenv.anyio.Path,
        mocker: MockerFixture,
        sort_dotenv: bool,
    ) -> None:
        """Assert that `load_dotenv` returns a `DotEnv` instance that is
        sorted if `sort_dotenv=True`, or unsorted if `sort_dotenv=False`.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(
            env_file_unsorted, sort_dotenv=sort_dotenv
        )
        dotenv_keys = list(dict(dotenv).keys())
        assert (dotenv_keys == sorted(dotenv_keys)) is sort_dotenv

    @pytest.mark.anyio
    async def test_load_dotenv_empty_file(
        self, env_file_empty: fastenv.dotenv.anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `load_dotenv` with a correct path
        to an empty file returns an empty `DotEnv` instance.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(env_file_empty, raise_exceptions=True)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        assert dotenv.source == env_file_empty
        assert isinstance(dotenv.source, fastenv.dotenv.anyio.Path)
        assert await dotenv.source.is_file()
        assert len(dotenv) == 0
        logger.info.assert_called_once_with(
            f"fastenv loaded 0 variables from {env_file_empty}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("output_key, output_value", dotenv_files_output)
    async def test_load_dotenv_files_in_same_dir(
        self,
        env_files_in_same_dir: list[fastenv.dotenv.anyio.Path],
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with paths to multiple source files
        loads the files, overwrites values of duplicate keys in left-to-right
        insertion order, and returns a `DotEnv` instance with all expected values.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(*env_files_in_same_dir)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert dotenv.source == env_files_in_same_dir
        for env_file in env_files_in_same_dir:
            assert isinstance(env_file, fastenv.dotenv.anyio.Path)
            assert await env_file.is_file()
        logger.info.assert_called_once_with(
            f"fastenv loaded 15 variables from {env_files_in_same_dir}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    async def test_load_dotenv_file_in_sub_dir(
        self,
        env_file: fastenv.dotenv.anyio.Path,
        env_file_child_dir: fastenv.dotenv.anyio.Path,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with a source file in a
        directory above and `find_source=True` finds and loads the file,
        and returns a `DotEnv` instance with all expected values.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        fastenv.dotenv.os.chdir(env_file_child_dir)
        dotenv = await fastenv.dotenv.load_dotenv(env_file.name, find_source=True)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)
        assert dotenv.source == env_file
        logger.info.assert_called_once_with(
            f"fastenv loaded {len(dotenv_args)} variables from {env_file}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("output_key, output_value", dotenv_files_output)
    async def test_load_dotenv_files_in_sub_dirs(
        self,
        env_file_child_dir: fastenv.dotenv.anyio.Path,
        env_files_in_child_dirs: list[fastenv.dotenv.anyio.Path],
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with paths to multiple source files
        in multiple directories and `find_source=True` finds and loads the files,
        overwrites values of duplicate keys in left-to-right insertion order, and
        returns a `DotEnv` instance with all expected values.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        filenames = tuple(file.name for file in env_files_in_child_dirs)
        fastenv.dotenv.os.chdir(env_file_child_dir)
        dotenv = await fastenv.dotenv.load_dotenv(*filenames, find_source=True)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert dotenv.source == env_files_in_child_dirs
        logger.info.assert_called_once_with(
            f"fastenv loaded 6 variables from {env_files_in_child_dirs}"
        )

    @pytest.mark.anyio
    async def test_load_dotenv_files_in_other_dirs_no_find(
        self,
        env_file_child_dir: fastenv.dotenv.anyio.Path,
        env_files_in_child_dirs: list[fastenv.dotenv.anyio.Path],
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with paths to multiple source files
        in multiple directories and `find_source=False` raises `FileNotFoundError`.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        for env_file in env_files_in_child_dirs:
            assert await env_file.is_file()
        filenames = tuple(file.name for file in env_files_in_child_dirs)
        fastenv.dotenv.os.chdir(env_file_child_dir)
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.load_dotenv(*filenames, find_source=False)
        assert "FileNotFoundError" in logger.error.call_args.args[0]
        assert str(e.value) in logger.error.call_args.args[0]

    @pytest.mark.anyio
    async def test_load_dotenv_incorrect_path_no_raise(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that calling `load_dotenv` with an incorrect path and
        `raise_exceptions=False` returns an empty `DotEnv` instance.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv("/not/a/file", raise_exceptions=False)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        assert not dotenv.source
        assert len(dotenv) == 0
        assert "FileNotFoundError" in logger.error.call_args.args[0]

    @pytest.mark.anyio
    async def test_load_dotenv_incorrect_path_with_raise(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that calling `load_dotenv` with an incorrect path and
        `raise_exceptions=True` raises an exception.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.load_dotenv("/not/a/file", raise_exceptions=True)
        assert "FileNotFoundError" in logger.error.call_args.args[0]
        assert str(e.value) in logger.error.call_args.args[0]

    @pytest.mark.anyio
    async def test_dotenv_values_with_dotenv_instance(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that a `DotEnv` instance serializes into a dictionary as expected."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        result = await fastenv.dotenv.dotenv_values(dotenv)
        assert result == dict(dotenv) == input_kwargs

    @pytest.mark.anyio
    @pytest.mark.parametrize("sort_dotenv", (False, True))
    async def test_dotenv_values_with_dotenv_instance_sorted(
        self, mocker: MockerFixture, sort_dotenv: bool
    ) -> None:
        """Assert that a `DotEnv` instance serializes into a dictionary as expected."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv("zzz=123", **input_kwargs)
        result = await fastenv.dotenv.dotenv_values(dotenv, sort_dotenv=sort_dotenv)
        dotenv_keys = list(result.keys())
        assert (dotenv_keys == sorted(dotenv_keys)) is sort_dotenv

    @pytest.mark.anyio
    async def test_dotenv_values_with_env_file_path_and_mock_load(
        self, env_file_empty: fastenv.dotenv.anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `dotenv_values` with a path also calls `load_dotenv`."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        load_dotenv = mocker.patch.object(
            fastenv.dotenv,
            "load_dotenv",
            return_value=fastenv.dotenv.DotEnv("KEY1=value1"),
        )
        result = await fastenv.dotenv.dotenv_values(env_file_empty)
        load_dotenv.assert_called_once()
        assert result == {"KEY1": "value1"}

    @pytest.mark.anyio
    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    async def test_dotenv_values_with_env_file_path(
        self,
        env_file: fastenv.dotenv.anyio.Path,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `dotenv_values` with a path loads variables from
        the file at the given path into a `DotEnv` instance, and serializes the
        `DotEnv` instance into a dictionary as expected.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        result = await fastenv.dotenv.dotenv_values(env_file)
        assert isinstance(result, dict)
        assert result[output_key] == output_value
        assert environ[output_key] == output_value
        assert len(result) == len(dotenv_args)
        logger.info.assert_called_once_with(
            f"fastenv loaded {len(dotenv_args)} variables from {env_file}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("sort_dotenv", (False, True))
    async def test_dotenv_values_with_env_file_path_sorted(
        self,
        env_file_unsorted: fastenv.dotenv.anyio.Path,
        mocker: MockerFixture,
        sort_dotenv: bool,
    ) -> None:
        """Assert that `dotenv_values` returns a `DotEnv` instance that is
        sorted if `sort_dotenv=True`, or unsorted if `sort_dotenv=False`.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        result = await fastenv.dotenv.dotenv_values(
            env_file_unsorted, sort_dotenv=sort_dotenv
        )
        assert isinstance(result, dict)
        dotenv_keys = list(result.keys())
        assert (dotenv_keys == sorted(dotenv_keys)) is sort_dotenv

    @pytest.mark.anyio
    async def test_dump_dotenv_str(
        self, env_file: fastenv.dotenv.anyio.Path, env_str: str, mocker: MockerFixture
    ) -> None:
        """Assert that calling `dump_dotenv` with a string containing keys and values
        successfully writes to a file at the expected destination.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        destination = env_file.parent / ".env.dumpedstring"
        await fastenv.dotenv.dump_dotenv(env_str, destination)
        logger.info.assert_called_once_with(f"fastenv dumped to {destination}")

    @pytest.mark.anyio
    @pytest.mark.parametrize("input_arg, output_key, output_value", dotenv_args)
    async def test_dump_dotenv_file(
        self,
        env_file: fastenv.dotenv.anyio.Path,
        input_arg: str,
        output_key: str,
        output_value: str,
        mocker: MockerFixture,
    ) -> None:
        """Dump a `DotEnv` instance to a file, load the file into a new `DotEnv`
        instance, and assert that the new `DotEnv` instance has the expected contents.
        """
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv_source = fastenv.dotenv.DotEnv(*input_args)
        destination = env_file.parent / ".env.dumped"
        dump = await fastenv.dotenv.dump_dotenv(dotenv_source, destination)
        result = await fastenv.dotenv.load_dotenv(dump)
        assert variable_is_set(result, environ, output_key, output_value)

    @pytest.mark.anyio
    @pytest.mark.parametrize("sort_dotenv", (False, True))
    async def test_dump_dotenv_file_sorted(
        self,
        env_file: fastenv.dotenv.anyio.Path,
        env_str_unsorted: str,
        mocker: MockerFixture,
        sort_dotenv: bool,
    ) -> None:
        """Dump a `DotEnv` instance to a file, load the file into a new `DotEnv`
        instance, and assert that the new `DotEnv` instance is sorted as expected.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv_source = fastenv.dotenv.DotEnv(env_str_unsorted)
        destination = env_file.parent / ".env.dumpedandsorted"
        dump = await fastenv.dotenv.dump_dotenv(
            dotenv_source, destination, sort_dotenv=sort_dotenv
        )
        dotenv = await fastenv.dotenv.load_dotenv(dump)
        dotenv_keys = list(dict(dotenv).keys())
        assert (dotenv_keys == sorted(dotenv_keys)) is sort_dotenv

    @pytest.mark.anyio
    async def test_dump_dotenv_incorrect_path_with_raise(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that calling `dump_dotenv` with an incorrect destination
        and `raise_exceptions=True` raises an exception.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        source = fastenv.dotenv.DotEnv()
        destination = "s3://mybucket/.env"
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.dump_dotenv(source, destination, raise_exceptions=True)
        assert "FileNotFoundError" in logger.error.call_args.args[0]
        assert str(e.value) in logger.error.call_args.args[0]

    @pytest.mark.anyio
    async def test_dump_dotenv_incorrect_path_no_raise(
        self, mocker: MockerFixture, tmp_path: fastenv.dotenv.anyio.Path
    ) -> None:
        """Assert that calling `dump_dotenv` with an incorrect destination
        and `raise_exceptions=False` returns a `pathlib.Path` instance.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        source = fastenv.dotenv.DotEnv()
        destination = fastenv.dotenv.anyio.Path("s3://mybucket/.env")
        result = await fastenv.dotenv.dump_dotenv(
            source, destination, raise_exceptions=False
        )
        assert isinstance(result, fastenv.dotenv.anyio.Path)
        assert "FileNotFoundError" in logger.error.call_args.args[0]
