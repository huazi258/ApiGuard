"""Smoke tests for the installed package."""


def test_package_imports() -> None:
    import apiguard

    assert apiguard.__version__ == "0.1.0"
