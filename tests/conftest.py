"""
Pytest configuration and fixtures for the test suite.
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require database)"
    )
