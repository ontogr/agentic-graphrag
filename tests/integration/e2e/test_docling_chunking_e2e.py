"""E2E Docling chunking: settings, headings, fingerprinted ids and update on Neo4j.

The scenario ingests a real PDF (this needs the docling models) with a fake extractor
and embedder and shows that:

- chunks record the docling chunker, page provenance and the heading above them,
- every chunk is within the default token budget, counted with the shared tokenizer,
- ``update()`` with a smaller ``max_tokens`` and the same PDF re-chunks: the old
  chunks close, the new ids differ and no old chunk stays current,
- ``update()`` with the same settings is a no-op.

Document keys are unique per run and cleanup removes only what this run created. The
test writes its outcome to ``reports/e2e/docling_chunking.json``.
"""

import importlib.util
import shutil
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest

from agrag.chunking import (
    DEFAULT_CHUNKING,
    Chunking,
    ChunkingRule,
    DoclingChunker,
    RuleMatch,
)
from agrag.chunking.docling import _build_tokenizer
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact
from tests.integration.e2e.test_chunking_e2e import _cleanup, _Env, _HashEmbedder


docling_missing = importlib.util.find_spec("docling") is None
neo4j_missing = importlib.util.find_spec("neo4j") is None

_PDF = Path(__file__).parents[1] / "loaders" / "corpus" / "fixtures" / "multi_page.pdf"


def _docling_chunking(chunker: DoclingChunker) -> Chunking:
    return Chunking(
        rules=[
            ChunkingRule(match=RuleMatch(loader_names=["docling"]), chunker=chunker)
        ],
        fallback=DEFAULT_CHUNKING.fallback,
    )


@pytest.mark.skipif(
    docling_missing or neo4j_missing, reason="docling or neo4j extra not installed"
)
class TestDoclingChunkingE2E:
    """Docling chunk settings and re-chunking through the public Graph API."""

    @pytest.fixture
    async def env(self, tmp_path: Path) -> AsyncGenerator[_Env, None]:
        """Open a store and a folder that holds the PDF."""
        run = uuid4().hex[:8]
        label = validate_identifier(f"Topic_{run}")
        schema = GraphSchema(
            name="docling_chunking",
            version="1",
            entities=[EntityType(label=label, description="A topic.")],
            relations=[],
        )
        store = build_graph_store("neo4j")
        root = tmp_path / f"corpus_{run}"
        root.mkdir()
        shutil.copy(_PDF, root / "report.pdf")
        env = _Env(run, store, schema, _HashEmbedder(), root)
        try:
            yield env
        finally:
            try:
                await _cleanup(env)
                await drop_schema_for(store, label)
            finally:
                await store.close()

    async def test_pdf_chunks_have_headings_and_rechunk_on_new_settings(
        self, env: _Env
    ) -> None:
        """Default chunks fit the budget and carry headings; new settings re-chunk."""
        key = str(env.root / "report.pdf")
        default_chunker = DEFAULT_CHUNKING.rules[0].chunker
        assert isinstance(default_chunker, DoclingChunker)
        graph = await env.open_graph()

        added = await graph.add(source=env.root)

        rows = await env.chunk_rows(key)
        assert rows
        assert {r["chunker"] for r in rows} == {"docling"}
        assert {r["chunker_hash"] for r in rows} == {default_chunker.fingerprint()}
        assert added.chunking.documents_by_rule == {"rule 0": 1}
        tokenizer = _build_tokenizer(default_chunker.tokenizer, 1024)
        assert all(tokenizer.count_tokens(r["text"]) <= 1024 for r in rows)
        headings = await env.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
            "WHERE r.invalid_at IS NULL RETURN c.heading_path AS path",
            {"key": key},
        )
        assert any(row["path"] for row in headings)

        # The same PDF and settings change nothing.
        assert (await graph.update(key, source=env.root / "report.pdf")).no_op is True

        # A smaller budget re-chunks the unchanged PDF.
        small = DoclingChunker(max_tokens=64)
        small_graph = await env.open_graph(_docling_chunking(small))
        changed = await small_graph.update(key, source=env.root / "report.pdf")

        assert changed.no_op is False
        assert changed.chunks_closed == len(rows)
        new_rows = await env.chunk_rows(key)
        assert len(new_rows) > len(rows)
        assert {r["chunker_hash"] for r in new_rows} == {small.fingerprint()}
        assert not {str(r["id"]) for r in rows} & {str(r["id"]) for r in new_rows}
        assert (
            await small_graph.update(key, source=env.root / "report.pdf")
        ).no_op is True

        write_artifact(
            "docling_chunking",
            {
                "default": {
                    "chunker_hash": default_chunker.fingerprint(),
                    "chunks": len(rows),
                    "within_1024_tokens": True,
                    "has_heading_path": True,
                },
                "rechunked": {
                    "max_tokens": 64,
                    "chunker_hash": small.fingerprint(),
                    "chunks_closed": changed.chunks_closed,
                    "chunks_after": len(new_rows),
                    "old_ids_current": False,
                    "same_settings_update_no_op": True,
                },
            },
        )
