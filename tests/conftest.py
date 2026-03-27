"""
Pytest configuration and fixtures for the test suite.
"""



def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests (require database)")
