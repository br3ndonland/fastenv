from __future__ import annotations

import os
from typing import TYPE_CHECKING

import anyio
import pytest

import fastenv.dotenv

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from typing import Any

    from pytest_mock import MockerFixture


def variable_is_set(
    dotenv: fastenv.dotenv.DotEnv,
    environ: MutableMapping[str, str],
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
    assert os.getenv(expected_key) == expected_value
    return True


def variable_is_unset(
    dotenv: fastenv.dotenv.DotEnv,
    environ: MutableMapping[str, str],
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
    response: str | dict[str, str | None] | None,
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

    def test_instantiate_dotenv_class_with_arg(
        self, dotenv_arg: tuple[str, str, str], mocker: MockerFixture
    ) -> None:
        """Instantiate `class DotEnv` with a `"key=value"` string argument and
        assert that it is set in both `os.environ` and the `DotEnv` instance.
        """
        input_arg, output_key, output_value = dotenv_arg
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(input_arg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == 1

    def test_instantiate_dotenv_class_with_arg_incorrect_type(
        self,
        input_arg_incorrect_type: dict[str, str] | int | list[int],
        mocker: MockerFixture,
    ) -> None:
        """Assert that attempting to instantiate `class DotEnv`
        with any non-string arguments raises a `TypeError`.
        """
        mocker.patch.dict(os.environ, clear=True)
        with pytest.raises(TypeError) as e:
            fastenv.dotenv.DotEnv(input_arg_incorrect_type)  # type: ignore[arg-type]
        assert "Arguments passed to DotEnv instances should be strings" in str(e.value)

    def test_instantiate_dotenv_class_with_args(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        input_args: tuple[str, ...],
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with `"key=value"` string arguments and
        assert that each is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(*input_args)
        for input_arg, output_key, output_value in dotenv_args:
            assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args) == len(input_args)

    def test_instantiate_dotenv_class_with_kwarg(
        self, dotenv_kwarg: tuple[dict[str, str], str, str], mocker: MockerFixture
    ) -> None:  # sourcery skip: class-extract-method
        """Instantiate `class DotEnv` with a `key=value` keyword argument ("kwarg")
        and assert that it is set in both `os.environ` and the `DotEnv` instance.
        """
        input_kwarg, output_key, output_value = dotenv_kwarg
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwarg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == 1

    def test_instantiate_dotenv_class_with_kwarg_incorrect_type(
        self,
        dotenv_kwarg_incorrect_type: tuple[dict[str, Any], str, str],
        mocker: MockerFixture,
    ) -> None:
        """Assert that attempting to instantiate `class DotEnv` with a non-string kwarg
        converts the value to a string, sets the variable in both the `DotEnv` instance
        and `os.environ`, and returns a dict of the key and corresponding value set.
        """
        input_kwarg, output_key, output_value = dotenv_kwarg_incorrect_type
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwarg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == 1

    def test_instantiate_dotenv_class_with_kwargs(
        self,
        dotenv_kwargs: tuple[tuple[dict[str, str], str, str], ...],
        input_kwargs: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with `key=value` keyword arguments ("kwargs")
        and assert that each is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        for input_kwarg, output_key, output_value in dotenv_kwargs:
            assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_kwargs)

    def test_instantiate_dotenv_class_with_both_args_and_kwargs(
        self,
        dotenv_kwargs: tuple[tuple[dict[str, str], str, str], ...],
        input_kwargs: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with a combination of args and kwargs,
        assert that each is set in both `os.environ` and the `DotEnv` instance,
        and verify left-to-right mapping insertion order (kwargs override args).
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(
            "AWS_ACCESS_KEY_ID_EXAMPLE=OVERRIDETHIS1EXAMPLE", **input_kwargs
        )
        for input_kwarg, output_key, output_value in dotenv_kwargs:
            assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_kwargs)

    def test_instantiate_dotenv_class_with_string(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        env_str: str,
        mocker: MockerFixture,
    ) -> None:
        """Instantiate `class DotEnv` with a multi-variable string argument and assert
        that each variable is set in both `os.environ` and the `DotEnv` instance.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(env_str)
        for input_arg, output_key, output_value in dotenv_args:
            assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)

    def test_get_single_variable_unset(self, mocker: MockerFixture) -> None:
        """Assert that attempting to get an unset variable returns `None` from a call,
        and raises a `KeyError` when square bracket syntax is used.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        assert variable_is_unset(dotenv, environ, "unset")

    def test_get_variables(
        self, input_kwargs: dict[str, str], mocker: MockerFixture
    ) -> None:
        """Assert that calling a `DotEnv` instance with variable keys
        returns a dict containing the keys and corresponding values.
        """
        mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        assert dotenv(*input_kwargs.keys()) == input_kwargs
        for key, value in input_kwargs.items():
            assert dotenv.get(key) == value

    def test_get_and_set_variables_in_single_call(
        self, input_kwargs: dict[str, str], mocker: MockerFixture
    ) -> None:
        """Assert that calling a `DotEnv` instance with a combination of variables
        to get and set returns a dict containing the keys and corresponding values.
        """
        mocker.patch.dict(os.environ, clear=True)
        expected_result = {**input_kwargs, "KEY4": "value4"}
        dotenv = fastenv.dotenv.DotEnv("KEY4=value4")
        assert dotenv("KEY4", **input_kwargs) == expected_result
        for key, value in expected_result.items():
            assert dotenv.get(key) == value

    def test_set_variable_with_call(
        self, dotenv_arg: tuple[str, str, str], mocker: MockerFixture
    ) -> None:
        """Assert that setting a single variable with a call to a `DotEnv` instance
        sets the variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the key and corresponding value that were set.
        """
        input_arg, output_key, output_value = dotenv_arg
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(input_arg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    def test_set_variable_with_call_and_incorrect_type(
        self,
        input_arg_incorrect_type: dict[str, str] | int | list[int],
        mocker: MockerFixture,
    ) -> None:
        """Assert that attempting to call a `DotEnv` instance
        with any non-string arguments raises a `TypeError`.
        """
        mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        with pytest.raises(TypeError) as e:
            dotenv("KEY=value", input_arg_incorrect_type)  # type: ignore[arg-type]
        assert not len(dotenv)
        assert "Arguments passed to DotEnv instances should be strings" in str(e.value)

    def test_set_variable_with_square_brackets(
        self, dotenv_arg: tuple[str, str, str], mocker: MockerFixture
    ) -> None:
        """Assert that setting a single variable with square brackets
        sets the variable in both the `DotEnv` instance and `os.environ`.
        """
        input_arg, output_key, output_value = dotenv_arg
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        dotenv[output_key] = output_value
        assert variable_is_set(dotenv, environ, output_key, output_value)

    def test_set_variables_with_call_and_args(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        input_args: tuple[str, ...],
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(*input_args)
        for input_arg, output_key, output_value in dotenv_args:
            assert variable_is_set(dotenv, environ, output_key, output_value)
            assert response_is_correct(dotenv, response, output_key, output_value)
        assert len(dotenv) == len(dotenv_args) == len(input_args)

    def test_set_variables_with_call_and_kwargs(
        self,
        dotenv_kwargs: tuple[tuple[dict[str, str], str, str], ...],
        input_kwargs: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(**input_kwargs)
        for input_kwarg, output_key, output_value in dotenv_kwargs:
            assert variable_is_set(dotenv, environ, output_key, output_value)
            assert response_is_correct(dotenv, response, output_key, output_value)
        assert len(dotenv) == len(dotenv_kwargs)

    def test_set_variables_with_call_and_both_args_and_kwargs(
        self,
        dotenv_kwargs: tuple[tuple[dict[str, str], str, str], ...],
        input_kwargs: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(
            "AWS_ACCESS_KEY_ID_EXAMPLE=OVERRIDETHIS1EXAMPLE", **input_kwargs
        )
        for input_kwarg, output_key, output_value in dotenv_kwargs:
            assert variable_is_set(dotenv, environ, output_key, output_value)
            assert response_is_correct(dotenv, response, output_key, output_value)
        assert len(dotenv) == len(dotenv_kwargs)

    def test_set_variables_with_call_and_kwarg_incorrect_type(
        self,
        dotenv_kwarg_incorrect_type: tuple[dict[str, Any], str, str],
        mocker: MockerFixture,
    ) -> None:
        """Assert that attempting to set a variable with a non-string kwarg converts
        the value to a string, sets the variable in both the `DotEnv` instance and
        `os.environ`, and returns a dict of the key and corresponding value set.
        """
        input_kwarg, output_key, output_value = dotenv_kwarg_incorrect_type
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(**input_kwarg)
        assert variable_is_set(dotenv, environ, output_key, output_value)
        assert response_is_correct(dotenv, response, output_key, output_value)

    def test_set_variables_with_call_and_string(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        env_str: str,
        mocker: MockerFixture,
    ) -> None:
        """Assert that setting multiple variables with a call to a `DotEnv` instance
        sets each variable in both the `DotEnv` instance and `os.environ`, and that
        the call returns a dict of the keys and corresponding values that were set.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        response = dotenv(env_str)
        for input_arg, output_key, output_value in dotenv_args:
            assert variable_is_set(dotenv, environ, output_key, output_value)
            assert response_is_correct(dotenv, response, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)

    @pytest.mark.parametrize("comment", ("#no_spaces", "  #  spaces", "# key=value"))
    def test_set_variables_with_call_and_string_comments(
        self, comment: str, mocker: MockerFixture
    ) -> None:
        """Assert that comments are ignored when calling a `DotEnv` instance."""
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv()
        dotenv(comment)
        assert variable_is_unset(dotenv, environ, comment)

    def test_delete_variable(
        self, input_kwargs: dict[str, str], mocker: MockerFixture
    ) -> None:
        """Assert that deleting a variable from a `DotEnv` instance deletes the
        corresponding variable from both the `DotEnv` instance and `os.environ`.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        for key in input_kwargs:
            del dotenv[key]
            assert variable_is_unset(dotenv, environ, key)
        assert len(dotenv) == 0

    def test_delete_variables(
        self, input_kwargs: dict[str, str], mocker: MockerFixture
    ) -> None:
        """Assert that deleting variables from a `DotEnv` instance deletes the
        corresponding variables from both the `DotEnv` instance and `os.environ`.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        dotenv.delenv(*input_kwargs.keys())
        for key in input_kwargs:
            assert variable_is_unset(dotenv, environ, key)
        assert len(dotenv) == 0

    def test_delete_variables_skip_unset(self, mocker: MockerFixture) -> None:
        """Assert that unset variables are skipped when deleting `DotEnv` variables."""
        mocker.patch.dict(os.environ, clear=True)
        dotenv_delete_item = mocker.patch.object(
            fastenv.dotenv.DotEnv, "__delitem__", autospec=True
        )
        dotenv = fastenv.dotenv.DotEnv("EXAMPLE_KEY=example_value UNSET")
        assert dotenv.getenv("EXAMPLE_KEY")
        assert not (dotenv.getenv("UNSET") and os.getenv("UNSET"))
        dotenv.delenv("EXAMPLE_KEY", "UNSET")
        dotenv_delete_item.assert_called_once()
        assert "EXAMPLE_KEY" in dotenv_delete_item.call_args.args
        assert "UNSET" not in dotenv_delete_item.call_args.args

    def test_iter(self, input_kwargs: dict[str, str], mocker: MockerFixture) -> None:
        """Assert that calling the `__iter__` method on a
        `DotEnv` instance appropriately iterates over its keys.
        """
        mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        dotenv_iterator = iter(dotenv)
        assert list(dotenv) == list(input_kwargs.keys())
        for _ in input_kwargs:
            iteration_result = next(dotenv_iterator)
            assert iteration_result in input_kwargs
            assert isinstance(iteration_result, str)
        with pytest.raises(StopIteration):
            next(dotenv_iterator)

    def test_dict(self, input_kwargs: dict[str, str], mocker: MockerFixture) -> None:
        """Assert that a `DotEnv` instance serializes into a dictionary as expected."""
        mocker.patch.dict(os.environ, clear=True)
        dotenv = fastenv.dotenv.DotEnv(**input_kwargs)
        assert dict(dotenv) == input_kwargs


class TestDotEnvMethods:
    """Test methods associated with `class DotEnv`."""

    @pytest.mark.anyio
    async def test_find_dotenv_with_resolved_path_to_file(
        self, env_file: anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `find_dotenv` with a resolved filepath
        returns the path straight away without further iteration.
        """
        mocker.patch.dict(os.environ, clear=True)
        iterdir = mocker.patch.object(anyio.Path, "iterdir")
        resolved_path = await env_file.resolve()
        result = await fastenv.dotenv.find_dotenv(resolved_path)
        assert result == resolved_path
        iterdir.assert_not_called()

    @pytest.mark.anyio
    async def test_find_dotenv_with_file_in_same_dir(
        self, env_file: anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `find_dotenv` with the name of a dotenv file in the
        same directory returns the path straight away without further iteration.
        """
        mocker.patch.dict(os.environ, clear=True)
        iterdir = mocker.patch.object(anyio.Path, "iterdir")
        resolved_path = await env_file.resolve()
        os.chdir(env_file.parent)
        result = await fastenv.dotenv.find_dotenv(env_file.name)
        assert result == resolved_path
        iterdir.assert_not_called()

    @pytest.mark.anyio
    async def test_find_dotenv_with_file_from_sub_dir(
        self,
        env_file: anyio.Path,
        env_file_child_dir: anyio.Path,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `find_dotenv` from a sub-directory, with the name of
        a dotenv file in a directory above, returns the path to the dotenv file.
        """
        mocker.patch.dict(os.environ, clear=True)
        resolved_path = await env_file.resolve()
        os.chdir(env_file_child_dir)
        result = await fastenv.dotenv.find_dotenv(env_file.name)
        assert result == resolved_path

    @pytest.mark.anyio
    async def test_find_dotenv_no_file_with_raise(self, mocker: MockerFixture) -> None:
        """Assert that calling `find_dotenv` when the dotenv file cannot be found
        raises a `FileNotFoundError` with the filename included in the exception.
        """
        mocker.patch.dict(os.environ, clear=True)
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.find_dotenv(".env.nofile")
        assert ".env.nofile" in str(e.value)

    @pytest.mark.anyio
    async def test_load_dotenv_no_file_with_raise(self, mocker: MockerFixture) -> None:
        """Assert that calling `load_dotenv` with `find_source=True` and the
        name of a source file that does not exist raises `FileNotFoundError`.
        """
        mocker.patch.dict(os.environ, clear=True)
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
        mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(
            ".env.nofile", find_source=True, raise_exceptions=False
        )
        assert len(dotenv) == 0
        logger.error.assert_called_once_with(
            "fastenv error: FileNotFoundError Could not find .env.nofile"
        )

    @pytest.mark.anyio
    async def test_load_dotenv_file(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        env_file: anyio.Path,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with a correct path to a dotenv file
        returns a `DotEnv` instance with all expected variables set.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(env_file)
        for input_arg, output_key, output_value in dotenv_args:
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
        env_file_unsorted: anyio.Path,
        mocker: MockerFixture,
        sort_dotenv: bool,
    ) -> None:
        """Assert that `load_dotenv` returns a `DotEnv` instance that is
        sorted if `sort_dotenv=True`, or unsorted if `sort_dotenv=False`.
        """
        mocker.patch.dict(os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(
            env_file_unsorted, sort_dotenv=sort_dotenv
        )
        dotenv_keys = list(dict(dotenv).keys())
        assert (dotenv_keys == sorted(dotenv_keys)) is sort_dotenv

    @pytest.mark.anyio
    async def test_load_dotenv_empty_file(
        self, env_file_empty: anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `load_dotenv` with a correct path
        to an empty file returns an empty `DotEnv` instance.
        """
        mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(env_file_empty, raise_exceptions=True)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        assert dotenv.source == env_file_empty
        assert isinstance(dotenv.source, anyio.Path)
        assert await dotenv.source.is_file()
        assert len(dotenv) == 0
        logger.info.assert_called_once_with(
            f"fastenv loaded 0 variables from {env_file_empty}"
        )

    @pytest.mark.anyio
    async def test_load_dotenv_files_in_same_dir(
        self,
        env_files_in_same_dir: list[anyio.Path],
        env_files_output: tuple[tuple[str, str], ...],
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with paths to multiple source files
        loads the files, overwrites values of duplicate keys in left-to-right
        insertion order, and returns a `DotEnv` instance with all expected values.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = await fastenv.dotenv.load_dotenv(*env_files_in_same_dir)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        for output_key, output_value in env_files_output:
            assert variable_is_set(dotenv, environ, output_key, output_value)
        assert dotenv.source == env_files_in_same_dir
        for env_file in env_files_in_same_dir:
            assert isinstance(env_file, anyio.Path)
            assert await env_file.is_file()
        logger.info.assert_called_once_with(
            f"fastenv loaded 15 variables from {env_files_in_same_dir}"
        )

    @pytest.mark.anyio
    async def test_load_dotenv_file_in_sub_dir(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        env_file: anyio.Path,
        env_file_child_dir: anyio.Path,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with a source file in a
        directory above and `find_source=True` finds and loads the file,
        and returns a `DotEnv` instance with all expected values.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        os.chdir(env_file_child_dir)
        dotenv = await fastenv.dotenv.load_dotenv(env_file.name, find_source=True)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        for input_arg, output_key, output_value in dotenv_args:
            assert variable_is_set(dotenv, environ, output_key, output_value)
        assert len(dotenv) == len(dotenv_args)
        assert dotenv.source == env_file
        logger.info.assert_called_once_with(
            f"fastenv loaded {len(dotenv_args)} variables from {env_file}"
        )

    @pytest.mark.anyio
    async def test_load_dotenv_files_in_sub_dirs(
        self,
        env_file_child_dir: anyio.Path,
        env_files_in_child_dirs: list[anyio.Path],
        env_files_output: tuple[tuple[str, str], ...],
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with paths to multiple source files
        in multiple directories and `find_source=True` finds and loads the files,
        overwrites values of duplicate keys in left-to-right insertion order, and
        returns a `DotEnv` instance with all expected values.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        filenames = tuple(file.name for file in env_files_in_child_dirs)
        os.chdir(env_file_child_dir)
        dotenv = await fastenv.dotenv.load_dotenv(*filenames, find_source=True)
        assert isinstance(dotenv, fastenv.dotenv.DotEnv)
        for output_key, output_value in env_files_output:
            assert variable_is_set(dotenv, environ, output_key, output_value)
        assert dotenv.source == env_files_in_child_dirs
        logger.info.assert_called_once_with(
            f"fastenv loaded 6 variables from {env_files_in_child_dirs}"
        )

    @pytest.mark.anyio
    async def test_load_dotenv_files_in_other_dirs_no_find(
        self,
        env_file_child_dir: anyio.Path,
        env_files_in_child_dirs: list[anyio.Path],
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `load_dotenv` with paths to multiple source files
        in multiple directories and `find_source=False` raises `FileNotFoundError`.
        """
        mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        for env_file in env_files_in_child_dirs:
            assert await env_file.is_file()
        filenames = tuple(file.name for file in env_files_in_child_dirs)
        os.chdir(env_file_child_dir)
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
        mocker.patch.dict(os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        await fastenv.dotenv.load_dotenv("/not/a/file", raise_exceptions=False)

    @pytest.mark.anyio
    async def test_load_dotenv_incorrect_path_with_raise(
        self, mocker: MockerFixture
    ) -> None:
        """Assert that calling `load_dotenv` with an incorrect path and
        `raise_exceptions=True` raises an exception.
        """
        mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.load_dotenv("/not/a/file", raise_exceptions=True)
        assert "FileNotFoundError" in logger.error.call_args.args[0]
        assert str(e.value) in logger.error.call_args.args[0]

    @pytest.mark.anyio
    @pytest.mark.parametrize("sort_dotenv", (False, True))
    async def test_dotenv_values_with_dotenv_instance_and_sorting(
        self, input_kwargs: dict[str, str], mocker: MockerFixture, sort_dotenv: bool
    ) -> None:
        """Assert that a `DotEnv` instance serializes into a dictionary as expected."""
        mocker.patch.dict(os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        dotenv = fastenv.dotenv.DotEnv("zzz=123", **input_kwargs)
        result = await fastenv.dotenv.dotenv_values(dotenv, sort_dotenv=sort_dotenv)
        dotenv_keys = list(result.keys())
        assert (dotenv_keys == sorted(dotenv_keys)) is sort_dotenv

    @pytest.mark.anyio
    async def test_dotenv_values_with_env_file_path_and_mock_load(
        self, env_file_empty: anyio.Path, mocker: MockerFixture
    ) -> None:
        """Assert that calling `dotenv_values` with a path also calls `load_dotenv`."""
        mocker.patch.dict(os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        load_dotenv = mocker.patch.object(
            fastenv.dotenv,
            "load_dotenv",
            return_value=fastenv.dotenv.DotEnv("KEY1=value1"),
        )
        result = await fastenv.dotenv.dotenv_values(env_file_empty)
        load_dotenv.assert_called_once()
        assert result == {"KEY1": "value1"}

    @pytest.mark.anyio
    async def test_dotenv_values_with_env_file_path(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        env_file: anyio.Path,
        mocker: MockerFixture,
    ) -> None:
        """Assert that calling `dotenv_values` with a path loads variables from
        the file at the given path into a `DotEnv` instance, and serializes the
        `DotEnv` instance into a dictionary as expected.
        """
        environ = mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        result = await fastenv.dotenv.dotenv_values(env_file)
        assert isinstance(result, dict)
        for input_arg, output_key, output_value in dotenv_args:
            assert result[output_key] == output_value
            assert environ[output_key] == output_value
        assert len(result) == len(dotenv_args)
        logger.info.assert_called_once_with(
            f"fastenv loaded {len(dotenv_args)} variables from {env_file}"
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize("sort_dotenv", (False, True))
    async def test_dotenv_values_with_env_file_path_and_sorting(
        self,
        env_file_unsorted: anyio.Path,
        mocker: MockerFixture,
        sort_dotenv: bool,
    ) -> None:
        """Assert that `dotenv_values` returns a `DotEnv` instance that is
        sorted if `sort_dotenv=True`, or unsorted if `sort_dotenv=False`.
        """
        mocker.patch.dict(os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        result = await fastenv.dotenv.dotenv_values(
            env_file_unsorted, sort_dotenv=sort_dotenv
        )
        assert isinstance(result, dict)
        dotenv_keys = list(result.keys())
        assert (dotenv_keys == sorted(dotenv_keys)) is sort_dotenv

    @pytest.mark.anyio
    async def test_dump_dotenv_str(
        self, env_file: anyio.Path, env_str: str, mocker: MockerFixture
    ) -> None:
        """Assert that calling `dump_dotenv` with a string containing keys and values
        successfully writes to a file at the expected destination.
        """
        mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        destination = env_file.parent / ".env.dumpedstring"
        await fastenv.dotenv.dump_dotenv(env_str, destination)
        logger.info.assert_called_once_with(f"fastenv dumped to {destination}")

    @pytest.mark.anyio
    async def test_dump_dotenv_file(
        self,
        dotenv_args: tuple[tuple[str, str, str], ...],
        env_file: anyio.Path,
        input_args: tuple[str, ...],
        mocker: MockerFixture,
    ) -> None:
        """Dump a `DotEnv` instance to a file, load the file into a new `DotEnv`
        instance, and assert that the new `DotEnv` instance has the expected contents.
        """
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        environ = mocker.patch.dict(os.environ, clear=True)
        dotenv_source = fastenv.dotenv.DotEnv(*input_args)
        destination = env_file.parent / ".env.dumped"
        dump = await fastenv.dotenv.dump_dotenv(dotenv_source, destination)
        result = await fastenv.dotenv.load_dotenv(dump)
        for input_arg, output_key, output_value in dotenv_args:
            assert variable_is_set(result, environ, output_key, output_value)

    @pytest.mark.anyio
    @pytest.mark.parametrize("sort_dotenv", (False, True))
    async def test_dump_dotenv_file_with_sorting(
        self,
        env_file: anyio.Path,
        env_str_unsorted: str,
        mocker: MockerFixture,
        sort_dotenv: bool,
    ) -> None:
        """Dump a `DotEnv` instance to a file, load the file into a new `DotEnv`
        instance, and assert that the new `DotEnv` instance is sorted as expected.
        """
        mocker.patch.dict(os.environ, clear=True)
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
        mocker.patch.dict(os.environ, clear=True)
        logger = mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        source = fastenv.dotenv.DotEnv()
        destination = "s3://mybucket/.env"
        with pytest.raises(FileNotFoundError) as e:
            await fastenv.dotenv.dump_dotenv(source, destination, raise_exceptions=True)
        assert "FileNotFoundError" in logger.error.call_args.args[0]
        assert str(e.value) in logger.error.call_args.args[0]

    @pytest.mark.anyio
    async def test_dump_dotenv_incorrect_path_no_raise(
        self, mocker: MockerFixture, tmp_path: anyio.Path
    ) -> None:
        """Assert that calling `dump_dotenv` with an incorrect destination
        and `raise_exceptions=False` returns a `pathlib.Path` instance.
        """
        mocker.patch.dict(os.environ, clear=True)
        mocker.patch.object(fastenv.dotenv, "logger", autospec=True)
        source = fastenv.dotenv.DotEnv()
        destination = anyio.Path("s3://mybucket/.env")
        await fastenv.dotenv.dump_dotenv(source, destination, raise_exceptions=False)
