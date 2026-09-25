"""Tests for the import guard of ``agrag.eval``.

Blocks the ``deepeval`` import through ``sys.modules`` so the guard runs as it
does in an environment without the ``eval`` extra.
"""

import importlib
import sys

import pytest


class TestImportGuard:
    """Importing agrag.eval without deepeval names the missing extra."""

    def test_names_the_extra_when_deepeval_is_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The error tells the caller which extra to install."""
        monkeypatch.setitem(sys.modules, "deepeval", None)
        monkeypatch.delitem(sys.modules, "agrag.eval", raising=False)

        with pytest.raises(ImportError, match=r"agentic-graphrag\[eval\]"):
            importlib.import_module("agrag.eval")
