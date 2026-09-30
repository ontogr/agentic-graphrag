"""Fixtures for executing the Python blocks in the docs pages.

A block opts in with a fence such as ``python fixture:llm_env``.
"""

import os

import pytest


@pytest.fixture
def llm_env():
    """Skip a doc block unless an LLM endpoint is configured."""
    if not (os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL")):
        pytest.skip("LLM_BASE_URL and LLM_API_KEY are not set")
