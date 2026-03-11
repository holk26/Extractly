"""Shared pytest fixtures for the test suite.

The ``bypass_auth`` fixture is applied automatically to every test so that
existing tests don't need a valid PocketBase token.  Tests in
``test_auth.py`` override this behaviour to exercise real auth logic.
"""

import pytest

from app.dependencies.auth import require_auth
from app.main import app


@pytest.fixture(autouse=True)
def bypass_auth():
    """Replace ``require_auth`` with a no-op for all tests by default."""
    app.dependency_overrides[require_auth] = lambda: None
    yield
    app.dependency_overrides.pop(require_auth, None)
