import fastenv.types


def test_type_checking_attrs() -> None:
    """Verify basic import functionality and attributes of the types module.

    Type annotations are not used at runtime. The standard library `typing` module
    includes a `TYPE_CHECKING` constant that is `False` at runtime, or `True` when
    conducting static type checking prior to runtime. The types module will
    therefore have `TYPE_CHECKING == False` when tests are running, but should
    still make its public types available for other modules to import.

    The `type: ignore[attr-defined]` comment is needed to allow `implicit_reexport`
    for mypy. The types module imports `typing.TYPE_CHECKING`, but does not
    re-export it. Mypy would therefore raise an error in strict mode.

    https://docs.python.org/3/library/typing.html
    https://mypy.readthedocs.io/en/stable/config_file.html
    """
    assert fastenv.types.TYPE_CHECKING is False  # type: ignore[attr-defined]
    for attr in ("UploadPolicy", "UploadPolicyConditions"):
        assert hasattr(fastenv.types, attr)
