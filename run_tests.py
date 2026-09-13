"""Thin convenience wrapper around pytest.

This used to hand-list every test function and call them one by one,
which meant it silently stopped covering new tests the moment someone
added a file under tests/ without also editing this file. pytest (already
a `dev` extra in pyproject.toml) discovers tests on its own — this script
just exists for `python run_tests.py` muscle memory; `pytest` directly
works identically and is the canonical way to run the suite.
"""
import sys

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(["tests/"] + sys.argv[1:]))
