"""Keep the Trace spans page complete.

Every span name that agrag opens must appear on the reference page, so a new span
cannot ship without documentation.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "docs" / "docs" / "reference" / "trace-spans.mdx"
SPAN_NAME = re.compile(r'span\(\s*(?:[\w.]+\s*,\s*)?"(agrag\.[a-z_]+\.[a-z_.]+)"')


def _span_names() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "agrag").rglob("*.py"):
        if "baml_client" in path.parts:
            continue
        names.update(SPAN_NAME.findall(path.read_text(encoding="utf-8")))
    return names


def test_every_span_name_is_documented() -> None:
    """Fail when code opens a span that the reference page does not list."""
    page = PAGE.read_text(encoding="utf-8")
    missing = sorted(
        name
        for name in _span_names()
        if not re.search(rf"(?<![\w.]){re.escape(name)}(?!\w)", page)
    )
    assert not missing, f"Add these spans to trace-spans.mdx: {missing}"
