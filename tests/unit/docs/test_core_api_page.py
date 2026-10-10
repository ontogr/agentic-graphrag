"""Guard that every import line on the Core API page still resolves."""

import re
from pathlib import Path

import pytest


_PAGE = Path(__file__).parents[3] / "docs" / "docs" / "api" / "index.md"
_IMPORTS = re.findall(r"`(from agrag[\w.]* import [^`]+)`", _PAGE.read_text())


@pytest.mark.parametrize("line", _IMPORTS)
def test_import_line_resolves(line: str) -> None:
    """Each documented import works in the installed package."""
    try:
        exec(line, {})
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("agrag"):
            raise
        pytest.skip(f"optional dependency not installed: {error.name}")
