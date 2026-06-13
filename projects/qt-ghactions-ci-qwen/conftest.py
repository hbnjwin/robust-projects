"""Root conftest — registers custom markers and provides shared fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def _skip_integration(request):
    """Automatically skip integration tests when DATABASE_URL is not set."""
    marker = request.node.get_closest_marker("integration")
    if marker and not os.getenv("DATABASE_URL"):
        pytest.skip("PostgreSQL not available (DATABASE_URL not set)")
