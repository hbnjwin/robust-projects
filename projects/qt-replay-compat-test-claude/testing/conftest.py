import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow (skip with -m 'not slow')")
