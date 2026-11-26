#!/usr/bin/env python3
"""Script to run the tests."""

import sys

import pytest

# Change PYTHONPATH to include dependencies.
sys.path.insert(0, ".")

import utils.dependencies  # pylint: disable=wrong-import-position

if __name__ == "__main__":
    print(f"Using Python version {sys.version!s}")

    dependency_helper = utils.dependencies.DependencyHelper()

    if not dependency_helper.CheckTestDependencies():
        sys.exit(1)

    sys.exit(pytest.main(sys.argv[1:]))
