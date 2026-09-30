"""Guard that every import line on the Core API page still resolves."""

import re
from pathlib import Path

import pytest


_PAGE = Path(__file__).parents[3] / "docs" / "docs" / "api" / "index.md"
_IMPORTS = re.findall(r"`(from agrag[\w.]* import [^`]+)`", _PAGE.read_text())


def test_page_lists_the_entry_points() -> None:
    """The page carries the entry-point and result imports."""
    assert len(_IMPORTS) >= 15


@pytest.mark.parametrize("line", _IMPORTS)
def test_import_line_resolves(line: str) -> None:
    """Each documented import works in the installed package."""
    try:
        exec(line, {})
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("agrag"):
            raise
        pytest.skip(f"optional dependency not installed: {error.name}")
