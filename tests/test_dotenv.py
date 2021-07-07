from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

import fastenv.dotenv

dotenv_args: tuple[tuple[str, str, str], ...] = (
    (
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n",
        "AWS_ACCESS_KEY_ID",
        "AKIAIOSFODNN7EXAMPLE",
    ),
    (
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE\n",
        "AWS_SECRET_ACCESS_KEY",
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

dotenv_args_with_incorrect_types: tuple = ({"key": "value"}, 123, [1, 2, 3])

dotenv_kwargs_with_incorrect_types: tuple[tuple[dict, str, str], ...] = (
    ({"dict": {"key": "value"}}, "DICT", "{'key': 'value'}"),
    ({"int": 123}, "INT", "123"),
    ({"list": [1, 2, 3]}, "LIST", "[1, 2, 3]"),
)


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
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
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
            fastenv.dotenv.DotEnv("KEY=value", input_arg)  # type: ignore[arg-type]
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
        input_args = tuple(arg[0] for arg in dotenv_args)
        dotenv = fastenv.dotenv.DotEnv(*input_args)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
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
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
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
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
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
        input_kwargs = {arg[1]: arg[2] for arg in dotenv_args}
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
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
        input_to_override = "AWS_ACCESS_KEY_ID=OVERRIDETHIS1EXAMPLE"
        input_args = tuple(arg[0] for arg in dotenv_args)
        input_kwargs = {arg[1]: arg[2] for arg in dotenv_args}
        dotenv = fastenv.dotenv.DotEnv(input_to_override, *input_args, **input_kwargs)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
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
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
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
        example_dict = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        dotenv = fastenv.dotenv.DotEnv(**example_dict)
        assert dotenv(*example_dict.keys()) == example_dict
        assert dotenv("KEY1 KEY2 KEY3 # inline comment") == example_dict
        for key in example_dict:
            assert dotenv.get(key) == example_dict[key]

    def test_get_and_set_variables(self, mocker: MockerFixture) -> None:
        """Assert that calling a `DotEnv` instance with a mixture of variables
        to get and set returns a dict containing the keys and corresponding values.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        example_dict = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        expected_result = {**example_dict, "KEY4": "value4"}
        dotenv = fastenv.dotenv.DotEnv("KEY4=value4")
        assert dotenv("KEY4", **example_dict) == expected_result
        for key in expected_result:
            assert dotenv.get(key) == expected_result[key]

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
        result = dotenv(input_arg)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
        assert result == {output_key: output_value}
        assert len(result) == len(dotenv) == 1

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
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value

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
        input_args = tuple(arg[0] for arg in dotenv_args)
        dotenv = fastenv.dotenv.DotEnv()
        result = dotenv(*input_args)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
        assert isinstance(result, dict)
        assert result == dict(dotenv)
        assert result[output_key] == output_value
        assert len(result) == len(dotenv) == len(dotenv_args)

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
        input_kwargs = {arg[1]: arg[2] for arg in dotenv_args}
        dotenv = fastenv.dotenv.DotEnv()
        result = dotenv(**input_kwargs)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
        assert isinstance(result, dict)
        assert result == dict(dotenv)
        assert result[output_key] == output_value
        assert len(result) == len(dotenv) == len(dotenv_args)

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
        input_to_override = "AWS_ACCESS_KEY_ID=OVERRIDETHIS1EXAMPLE"
        input_args = tuple(arg[0] for arg in dotenv_args)
        input_kwargs = {arg[1]: arg[2] for arg in dotenv_args}
        dotenv = fastenv.dotenv.DotEnv()
        result = dotenv(input_to_override, *input_args, **input_kwargs)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
        assert isinstance(result, dict)
        assert result == dict(dotenv)
        assert result[output_key] == output_value
        assert len(result) == len(dotenv) == len(dotenv_args)

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
        result = dotenv(**input_kwarg)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
        assert isinstance(result, dict)
        assert result == dict(dotenv)
        assert result[output_key] == output_value
        assert len(result) == len(dotenv) == len(input_kwarg) == 1

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
        result = dotenv(env_str)
        assert dotenv(output_key) == output_value
        assert dotenv[output_key] == output_value
        assert environ[output_key] == output_value
        assert environ.get(output_key) == output_value
        assert fastenv.dotenv.os.getenv(output_key) == output_value
        assert isinstance(result, dict)
        assert result == dict(dotenv)
        assert result[output_key] == output_value
        assert len(result) == len(dotenv) == len(dotenv_args)

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
        example_dict = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        dotenv = fastenv.dotenv.DotEnv(**example_dict)
        for key in example_dict:
            del dotenv[key]
            assert dotenv.get(key) is None
            assert dotenv.getenv(key, "not_set") == "not_set"
            assert environ.get(key) is None
            with pytest.raises(KeyError):
                dotenv[key]
        assert len(dotenv) == 0

    def test_delete_variables(self, mocker: MockerFixture) -> None:
        """Assert that deleting variables from a `DotEnv` instance deletes the
        corresponding variables from both the `DotEnv` instance and `os.environ`.
        """
        environ = mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        example_dict = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        dotenv = fastenv.dotenv.DotEnv(**example_dict)
        dotenv.delenv(*example_dict.keys())
        for key in example_dict:
            assert dotenv.get(key) is None
            assert dotenv.getenv(key, "not_set") == "not_set"
            assert environ.get(key) is None
            with pytest.raises(KeyError):
                dotenv[key]
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
        example_dict = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        dotenv = fastenv.dotenv.DotEnv(**example_dict)
        dotenv_iterator = iter(dotenv)
        assert list(dotenv) == list(example_dict.keys())
        for i in (
            next(dotenv_iterator),
            next(dotenv_iterator),
            next(dotenv_iterator),
        ):
            assert i in example_dict
            assert isinstance(i, str)
        with pytest.raises(StopIteration):
            next(dotenv_iterator)

    def test_dict(self, mocker: MockerFixture) -> None:
        """Assert that a `DotEnv` instance serializes into a dictionary as expected."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        example_dict = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        dotenv = fastenv.dotenv.DotEnv(**example_dict)
        assert dict(dotenv) == example_dict


class TestDotEnvMethods:
    """Test methods associated with `class DotEnv`."""

    def test_find_dotenv_todo(self, mocker: MockerFixture) -> None:
        """TODO"""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        with pytest.raises(NotImplementedError):
            fastenv.dotenv.find_dotenv("/not/a/file")

    @pytest.mark.anyio
    async def test_dump_dotenv_todo(
        self, env_file_empty: fastenv.dotenv.pathlib.Path, mocker: MockerFixture
    ) -> None:
        """TODO"""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        with pytest.raises(NotImplementedError):
            await fastenv.dotenv.dump_dotenv(dotenv, env_file_empty)

    @pytest.mark.anyio
    async def test_load_dotenv_todo(
        self, env_file_empty: fastenv.dotenv.pathlib.Path, mocker: MockerFixture
    ) -> None:
        """TODO"""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        with pytest.raises(NotImplementedError):
            await fastenv.dotenv.load_dotenv(env_file_empty)

    @pytest.mark.anyio
    async def test_load_dotenv_no_raise(
        self, env_file_empty: fastenv.dotenv.pathlib.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `load_dotenv` with a path and`raise_exceptions=False`
        returns an empty `DotEnv` instance.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        result = await fastenv.dotenv.load_dotenv(
            env_file_empty, raise_exceptions=False
        )
        assert isinstance(result, fastenv.dotenv.DotEnv)
        assert len(result) == 0

    @pytest.mark.anyio
    async def test_dotenv_values_with_dotenv_instance(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that a `DotEnv` instance serializes into a dictionary as expected."""
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        example_dict = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        dotenv = fastenv.dotenv.DotEnv(**example_dict)
        result = await fastenv.dotenv.dotenv_values(dotenv)
        assert result == dict(dotenv) == example_dict

    @pytest.mark.anyio
    async def test_dotenv_values_with_env_file_path_and_mock_load(
        self, env_file_empty: fastenv.dotenv.pathlib.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `dotenv_values` with a path instantiates a `DotEnv`
        instance, and serializes the `DotEnv` instance into a dictionary as expected.
        """
        mocker.patch.dict(fastenv.dotenv.os.environ, clear=True)
        load_dotenv = mocker.patch.object(
            fastenv.dotenv,
            "load_dotenv",
            return_value=fastenv.dotenv.DotEnv("KEY1=value1"),
        )
        result = await fastenv.dotenv.dotenv_values(env_file_empty)
        load_dotenv.assert_called_once()
        assert result == {"KEY1": "value1"}
