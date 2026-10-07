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


MODULE = (
    "---\ntitle: agrag.graphdb\nsidebar_position: 3\n---\n\n"
    "## `agrag.graphdb` \\{#agrag-graphdb}\n\nIntro.\n\n"
    "**Modules:**\n\n- [**cypher**](#agrag-graphdb-cypher) \u2013 Queries.\n\n"
    "### `agrag.graphdb.Store`\n\nA store.\n\n"
    "#### `agrag.graphdb.Store.close`\n\n```python\n### not a heading\n```\n\n"
    "### `agrag.graphdb.connect`\n\nOpens a store.\n\n"
    "### `agrag.graphdb.cypher`\n\nQuery loader.\n\n"
    "#### `agrag.graphdb.cypher.load`\n\nLoads a query.\n"
)


def test_split_gives_each_object_a_page_and_each_submodule_a_folder() -> None:
    """A package page becomes an index, one page per object, and submodule folders."""
    out = docs_api_links.split({"graphdb": MODULE})

    assert set(out) == {
        "graphdb/index",
        "graphdb/Store",
        "graphdb/connect",
        "graphdb/cypher/index",
        "graphdb/cypher/load",
    }
    assert "title: agrag.graphdb\nsidebar_position: 3" in out["graphdb/index"]
    assert "A store." not in out["graphdb/index"]
    store = out["graphdb/Store"]
    assert "title: agrag.graphdb.Store\nsidebar_label: Store\n" in store
    assert "\n# `agrag.graphdb.Store`\n" in store
    assert "\n## `agrag.graphdb.Store.close`\n" in store
    assert "```python\n### not a heading\n```" in store
    assert "\n# `agrag.graphdb.cypher`\n\nQuery loader." in out["graphdb/cypher/index"]
    assert "Query loader." not in out["graphdb/index"]


def test_links_between_split_pages_are_relative() -> None:
    """Links reach a page in the same folder or in a sibling folder."""
    pages = {
        "graphdb/index": "# `agrag.graphdb`\n\n[S](#agrag-graphdb-Store)\n",
        "graphdb/Store": (
            "# `agrag.graphdb.Store`\n\n"
            "[E](#agrag-embedding-Embedder) [C](#agrag-graphdb-connect)\n"
        ),
        "graphdb/connect": "# `agrag.graphdb.connect`\n",
        "embedding/Embedder": "# `agrag.embedding.Embedder`\n",
    }

    out = docs_api_links.rewrite(pages)

    assert "(Store.md)" in out["graphdb/index"]
    assert "(../embedding/Embedder.md)" in out["graphdb/Store"]
    assert "(connect.md)" in out["graphdb/Store"]


def test_rewrite_is_idempotent() -> None:
    """Running the rewriter on its own output changes nothing."""
    once = docs_api_links.rewrite(PAGES)

    assert docs_api_links.rewrite(once) == once


def test_example_blocks_lose_the_attributes_the_docs_site_rejects() -> None:
    """A raw class or markdown attribute on <details> clashes with the site's own."""
    pages = {
        "eval": (
            '<details class="example" open markdown="1">\n'
            "<summary>Example</summary>\n\n```python\nx = 1\n```\n\n</details>\n"
            '<details class="note" markdown="1">\n<summary>Note</summary>\n</details>\n'
        )
    }

    out = docs_api_links.rewrite(pages)["eval"]

    assert "<details open>\n<summary>Example</summary>" in out
    assert "<details>\n<summary>Note</summary>" in out
    assert "class=" not in out
    assert "markdown=" not in out


def test_member_headings_show_the_last_name_segment_and_keep_the_id() -> None:
    """Only the page title keeps the full dotted name."""
    pages = {
        "graphdb/Store": (
            "# `agrag.graphdb.Store` \\{#agrag-graphdb-Store}\n\n"
            "## `agrag.graphdb.Store.close` \\{#agrag-graphdb-Store-close}\n"
        )
    }

    out = docs_api_links.shorten(pages)["graphdb/Store"]

    assert "# `agrag.graphdb.Store` \\{#agrag-graphdb-Store}" in out
    assert "## `close` \\{#agrag-graphdb-Store-close}" in out


def test_a_re_exported_object_keeps_only_its_defining_page() -> None:
    """The package copy of a class goes, and links to it reach the defining page."""
    pages = {
        "pkg/Thing": "---\ntitle: agrag.pkg.Thing\n---\n"
        "\n# `agrag.pkg.Thing`\n\nA thing.\n\n## `agrag.pkg.Thing.run`\n",
        "pkg/mod/Thing": "---\ntitle: agrag.pkg.mod.Thing\n---\n"
        "\n# `agrag.pkg.mod.Thing`\n\nA thing.\n\n## `agrag.pkg.mod.Thing.run`\n",
        "pkg/mod/Other": "---\ntitle: agrag.pkg.mod.Other\n---\n"
        "\n# `agrag.pkg.mod.Other`\n\n[run](#agrag.pkg.Thing.run)\n",
        "pkg/index": "- [**Thing**](#agrag.pkg.Thing)\n",
    }

    out = docs_api_links.dedupe(pages)

    assert set(out) == {"pkg/mod/Thing", "pkg/mod/Other", "pkg/index"}
    assert "(#agrag.pkg.mod.Thing)" in out["pkg/index"]
    assert "(#agrag.pkg.mod.Thing.run)" in out["pkg/mod/Other"]


def test_same_named_objects_in_unrelated_modules_both_stay() -> None:
    """Two loggers with the same docs are not re-exports of each other."""
    text = "---\ntitle: agrag.{}.logger\n---\n\n# `agrag.{}.logger`\n\nA logger.\n"
    pages = {
        "a/logger": text.format("a", "a"),
        "b/c/logger": text.format("b.c", "b.c"),
    }

    assert set(docs_api_links.dedupe(pages)) == set(pages)
