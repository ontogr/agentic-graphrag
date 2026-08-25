"""Tests for the package version exposed by :mod:`agrag`."""

import re

import agrag


class TestVersion:
    """Verify that ``agrag.__version__`` reflects the installed distribution."""

    def test_exposes_a_pep440_version(self) -> None:
        """``__version__`` is a PEP 440 style version string."""
        assert re.fullmatch(r"\d+\.\d+\.\d+.*", agrag.__version__)

    def test_is_not_the_uninstalled_fallback(self) -> None:
        """A real install must not fall back to the source-tree placeholder.

        This fails if the package is importable only because the repo root is on
        ``sys.path`` (the flat-layout shadowing trap) rather than truly installed.
        """
        assert agrag.__version__ != "0.0.0.dev0"
