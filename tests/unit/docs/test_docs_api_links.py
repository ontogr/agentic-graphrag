"""Tests for the API page link rewriter that runs after griffe2md."""

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).parents[3] / ".github" / "scripts" / "docs_api_links.py"
_spec = importlib.util.spec_from_file_location("docs_api_links", _SCRIPT)
assert _spec is not None and _spec.loader is not None
docs_api_links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs_api_links)

PAGES = {
    "graphdb": (
        "### `agrag.graphdb.Store`\n\n"
        "Uses <code>[Embedder](#agrag.embedding.Embedder)</code>, "
        "<code>[Store](#agrag.graphdb.Store)</code> and "
        "<code>[str](#str)</code>.\n"
    ),
    "embedding": "### `agrag.embedding.Embedder`\n\nPlain text.\n",
}


def test_headings_get_ids_and_links_resolve() -> None:
    """Names get explicit ids, cross-page links gain a page, others lose the link."""
    out = docs_api_links.rewrite(PAGES)["graphdb"]

    assert "### `agrag.graphdb.Store` \\{#agrag-graphdb-Store}" in out
    assert "[Embedder](embedding.md#agrag-embedding-Embedder)" in out
    assert "[Store](#agrag-graphdb-Store)" in out
    assert "<code>str</code>" in out


def test_rewrite_is_idempotent() -> None:
    """Running the rewriter on its own output changes nothing."""
    once = docs_api_links.rewrite(PAGES)

    assert docs_api_links.rewrite(once) == once
