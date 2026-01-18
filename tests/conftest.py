"""
Pytest configuration and shared fixtures for HPDE Analytics CLI tests.
"""

import os
import sys

import pytest

# Add the package root to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up environment variables before and after tests."""
    # Store original values
    original_key = os.environ.get("MSR_CONSUMER_KEY")
    original_secret = os.environ.get("MSR_CONSUMER_SECRET")

    yield

    # Restore original values
    if original_key is not None:
        os.environ["MSR_CONSUMER_KEY"] = original_key
    elif "MSR_CONSUMER_KEY" in os.environ:
        del os.environ["MSR_CONSUMER_KEY"]

    if original_secret is not None:
        os.environ["MSR_CONSUMER_SECRET"] = original_secret
    elif "MSR_CONSUMER_SECRET" in os.environ:
        del os.environ["MSR_CONSUMER_SECRET"]
