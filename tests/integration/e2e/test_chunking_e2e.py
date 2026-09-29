"""E2E chunking: rules, recorded chunkers and chunking-aware update() on Neo4j.

The scenario writes a folder with a plain-text file and a Markdown file, then shows:

- ``DEFAULT_CHUNKING`` records the recursive chunker and its hash on every chunk node,
  and ``AddResult.chunking`` counts what the graph holds,
- a two-rule ``Chunking`` sends Markdown to the token chunker and the rest to the
  fallback, and every stored chunk text equals its source slice at its offsets,
- ``update()`` with the same content and the same chunking is a no-op,
- ``update()`` with the same content and different chunking closes the old chunks,
  and retrieval returns the new set only,
- chunks written before chunkers were recorded make ``update()`` a no-op,
- a 5,000 character chunk reaches the ledger whole.

The extractor and embedder are fake and deterministic. Document keys are unique per
run and cleanup removes only what this run created. The test writes its outcome to
``reports/e2e/chunking.json``.
"""

import hashlib
import importlib.util
import json
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.chunking import (
    DEFAULT_CHUNKING,
    Chunking,
    ChunkingRule,
    RecursiveChunker,
    RuleMatch,
    TokenChunker,
)
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, SourceFormat
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.retrieval.recipes import Recipe
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


neo4j_missing = importlib.util.find_spec("neo4j") is None

_CHUNK_RECIPE = Recipe(methods=["chunk"], limit=200)


class _HashEmbedder(Embedder):
    """Embedder whose 4-d vector comes from the hash of the text."""

    model = "hash"

    async def dimensions(self) -> int:
        """Return 4 dimensions, as the shared Chunk vector index expects."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Map each text to a fixed vector."""
        return [
            [byte / 255 + 0.01 for byte in hashlib.sha256(text.encode()).digest()[:4]]
            for text in texts
        ]


class _NoEntityExtractor(Extractor):
    """Extractor that finds nothing, so the scenario tests chunking alone."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return an empty result."""
        return ExtractionResult(entities=[], relations=[], extractor_name="e2e")


def _prose(name: str, sentences: int) -> str:
    return " ".join(
        f"Sentence {i} of the {name} file covers topic {i % 7} in some detail."
        for i in range(sentences)
    )


def _write_folder(root: Path) -> None:
    root.mkdir()
    (root / "notes.txt").write_text(_prose("notes", 60), encoding="utf-8")
    (root / "guide.md").write_text(
        f"# Guide\n\n{_prose('guide', 30)}\n\n## Usage\n\n{_prose('usage', 30)}\n",
        encoding="utf-8",
    )


@dataclass
class _Env:
    """Everything one test needs, scoped to one run id."""

    run: str
    store: GraphStore
    schema: GraphSchema
    embedder: _HashEmbedder
    root: Path

    async def open_graph(self, chunking: Chunking = DEFAULT_CHUNKING) -> Graph:
        """Open a graph on the run's schema with the given chunking."""
        return await Graph.open(
            schema=self.schema,
            graph_store=self.store,
            embedder=self.embedder,
            extractor=_NoEntityExtractor(),
            chunking=chunking,
        )

    def engine(self) -> SearchEngine:
        """Return a search engine over the shared store."""
        return SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=RetrievalSettings(chunk_top_k=200),
            graph_schema=self.schema,
        )

    async def chunk_rows(self, key: str, *, open_only: bool = True) -> list[dict]:
        """Return the chunk nodes of one document, ordered by index."""
        condition = "WHERE r.invalid_at IS NULL " if open_only else ""
        return await self.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
            + condition
            + "RETURN c.id AS id, c.index AS index, c.text AS text, "
            "c.provenance AS provenance, c.chunker AS chunker, "
            "c.chunker_hash AS chunker_hash ORDER BY c.index",
            {"key": key},
        )

    async def retrieved_chunk_ids(self, query: str, keys: list[str]) -> set[str]:
        """Return ids of this run's chunks that a chunk search finds."""
        document_ids = {Document.node_id_for(document_key=key): key for key in keys}
        results = await self.engine().search(query, _CHUNK_RECIPE)
        return {
            str(result.item.id)
            for result in results
            if isinstance(result.item, Chunk)
            and result.item.document_id in document_ids
        }


async def _cleanup(env: _Env) -> None:
    """Remove only the nodes this run created."""
    prefix = str(env.root)
    await env.store.execute_write(
        "MATCH (d:Document)-[:PART_OF]->(c:Chunk) "
        "WHERE d.document_key STARTS WITH $prefix DETACH DELETE c",
        {"prefix": prefix},
    )
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix DETACH DELETE d",
        {"prefix": prefix},
    )
    await env.store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        {"prefix": prefix},
    )


def _slice_matches(row: dict, source: str) -> bool:
    provenance = TextProvenance(**json.loads(row["provenance"]))
    return row["text"] == source[provenance.char_start : provenance.char_end]


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestChunkingE2E:
    """Chunking rules, transparency and update through the public Graph API."""

    @pytest.fixture
    async def env(self, tmp_path: Path) -> AsyncGenerator[_Env, None]:
        """Open a store and a folder of documents unique to this test."""
        run = uuid4().hex[:8]
        label = validate_identifier(f"Topic_{run}")
        schema = GraphSchema(
            name="chunking",
            version="1",
            entities=[EntityType(label=label, description="A topic.")],
            relations=[],
        )
        store = build_graph_store("neo4j")
        root = tmp_path / f"corpus_{run}"
        _write_folder(root)
        env = _Env(run, store, schema, _HashEmbedder(), root)
        try:
            yield env
        finally:
            try:
                await _cleanup(env)
                await drop_schema_for(store, label)
            finally:
                await store.close()

    async def test_rules_record_chunkers_and_update_follows_them(  # noqa: PLR0915
        self, env: _Env
    ) -> None:
        """Default and custom chunking are recorded, and update re-chunks on change."""
        artifact: dict[str, object] = {}
        notes_key = str(env.root / "notes.txt")
        guide_key = str(env.root / "guide.md")
        notes_text = (env.root / "notes.txt").read_text(encoding="utf-8")
        guide_text = (env.root / "guide.md").read_text(encoding="utf-8")

        # Step 1: the default chunking records the recursive chunker.
        default_graph = await env.open_graph()
        added = await default_graph.add(source=env.root)
        fallback_hash = DEFAULT_CHUNKING.fallback.fingerprint()
        rows = {key: await env.chunk_rows(key) for key in (notes_key, guide_key)}
        for key, text in ((notes_key, notes_text), (guide_key, guide_text)):
            assert rows[key]
            assert {r["chunker"] for r in rows[key]} == {"recursive"}
            assert {r["chunker_hash"] for r in rows[key]} == {fallback_hash}
            assert all(_slice_matches(r, text) for r in rows[key])
        stored = sum(len(v) for v in rows.values())
        assert added.chunking.chunks_by_strategy == {"recursive": stored}
        assert added.chunking.documents_by_rule == {"fallback": 2}
        assert added.chunking.matches_total == 2
        artifact["1_default"] = {
            "chunker_hash": fallback_hash,
            "chunks_by_document": {
                Path(key).name: len(value) for key, value in rows.items()
            },
            "chunking": added.chunking.model_dump(mode="json", exclude={"matches"}),
        }

        # Step 2: a Markdown rule sends the guide to the token chunker. The copy of
        # the folder has other document keys, so it is a fresh add.
        second_root = env.root.parent / f"{env.root.name}_rules"
        _write_folder(second_root)
        rule_chunking = Chunking(
            rules=[
                ChunkingRule(
                    match=RuleMatch(source_formats=[SourceFormat.MARKDOWN]),
                    chunker=TokenChunker(chunk_size=160, tokenizer="character"),
                )
            ],
            fallback=RecursiveChunker(chunk_size=1024, tokenizer="character"),
        )
        rule_graph = await env.open_graph(rule_chunking)
        rule_added = await rule_graph.add(source=second_root)
        rule_guide = str(second_root / "guide.md")
        rule_notes = str(second_root / "notes.txt")
        guide_rows = await env.chunk_rows(rule_guide)
        notes_rows = await env.chunk_rows(rule_notes)
        assert {r["chunker"] for r in guide_rows} == {"token"}
        assert {r["chunker"] for r in notes_rows} == {"recursive"}
        assert all(_slice_matches(r, guide_text) for r in guide_rows)
        assert all(_slice_matches(r, notes_text) for r in notes_rows)
        assert rule_added.chunking.documents_by_rule == {"rule 0": 1, "fallback": 1}
        assert rule_added.chunking.chunks_by_strategy == {
            "token": len(guide_rows),
            "recursive": len(notes_rows),
        }
        artifact["2_rules"] = {
            "guide": {"chunker": "token", "chunks": len(guide_rows)},
            "notes": {"chunker": "recursive", "chunks": len(notes_rows)},
            "chunking": rule_added.chunking.model_dump(
                mode="json", exclude={"matches"}
            ),
        }

        # Step 3: update with the same content and chunking changes nothing.
        same = await rule_graph.update(rule_guide, source=second_root / "guide.md")
        assert same.no_op is True
        assert [r["id"] for r in await env.chunk_rows(rule_guide)] == [
            r["id"] for r in guide_rows
        ]

        # Step 4: the same content under new chunking closes the old chunks and
        # retrieval returns only the new set.
        old_ids = {str(r["id"]) for r in guide_rows}
        new_chunking = Chunking(
            rules=[
                ChunkingRule(
                    match=RuleMatch(source_formats=[SourceFormat.MARKDOWN]),
                    chunker=TokenChunker(chunk_size=400, tokenizer="character"),
                )
            ],
            fallback=RecursiveChunker(chunk_size=1024, tokenizer="character"),
        )
        new_graph = await env.open_graph(new_chunking)
        changed = await new_graph.update(rule_guide, source=second_root / "guide.md")
        assert changed.no_op is False
        assert changed.chunks_closed == len(guide_rows)
        assert changed.previous_content_hash == changed.new_content_hash
        assert changed.add_result is not None
        assert changed.add_result.chunking.documents_by_rule == {"rule 0": 1}
        new_rows = await env.chunk_rows(rule_guide)
        new_ids = {str(r["id"]) for r in new_rows}
        assert new_rows
        assert len(new_rows) == changed.add_result.chunking.chunks_by_strategy["token"]
        assert len(new_rows) < len(guide_rows)
        assert {r["chunker_hash"] for r in new_rows} == {
            new_chunking.rules[0].chunker.fingerprint()
        }
        assert all(_slice_matches(r, guide_text) for r in new_rows)
        found = await env.retrieved_chunk_ids(new_rows[0]["text"], [rule_guide])
        assert found
        assert found <= new_ids
        assert not found & (old_ids - new_ids)
        artifact["4_rechunked"] = {
            "chunks_closed": changed.chunks_closed,
            "chunks_before": len(guide_rows),
            "chunks_after": len(new_rows),
            "new_chunker_hash": new_rows[0]["chunker_hash"],
            "retrieval_returns_only_new_chunks": True,
        }

        # Step 5: chunks written before chunkers were recorded make update() a
        # no-op, even under different chunking.
        await env.store.execute_write(
            "MATCH (:Document {document_key: $key})-[:PART_OF]->(c:Chunk) "
            "REMOVE c.chunker, c.chunker_hash",
            {"key": rule_guide},
        )
        legacy = await default_graph.update(rule_guide, source=second_root / "guide.md")
        assert legacy.no_op is True
        artifact["5_legacy_update_no_op"] = legacy.no_op

        write_artifact("chunking", artifact)

    async def test_rechunk_keeps_a_chunk_that_both_chunkings_produce(
        self, env: _Env
    ) -> None:
        """A short document has one span under any size, and it stays current."""
        short = env.root.parent / f"{env.root.name}_short"
        short.mkdir()
        body = _prose("short", 3)
        (short / "short.txt").write_text(body, encoding="utf-8")
        key = str(short / "short.txt")
        first = await env.open_graph(
            Chunking(fallback=RecursiveChunker(chunk_size=1024, tokenizer="character"))
        )
        second_chunking = Chunking(
            fallback=RecursiveChunker(chunk_size=512, tokenizer="character")
        )
        second = await env.open_graph(second_chunking)
        await first.add(source=short)
        (before,) = await env.chunk_rows(key)

        changed = await second.update(key, source=short / "short.txt")

        assert changed.no_op is False
        (after,) = await env.chunk_rows(key)
        assert after["id"] == before["id"]
        assert after["chunker_hash"] == second_chunking.fallback.fingerprint()
        found = await env.retrieved_chunk_ids(body, [key])
        assert found == {str(after["id"])}

    async def test_large_chunk_reaches_the_ledger_whole(self, env: _Env) -> None:
        """A 5,000 character chunk is stored, retrieved and rendered without a cut."""
        big = env.root.parent / f"{env.root.name}_big"
        big.mkdir()
        body = _prose("big", 90)[:5000]
        assert len(body) == 5000
        (big / "big.txt").write_text(body, encoding="utf-8")
        chunking = Chunking(
            fallback=RecursiveChunker(chunk_size=6000, tokenizer="character")
        )
        graph = await env.open_graph(chunking)
        key = str(big / "big.txt")

        await graph.add(source=big)

        (row,) = await env.chunk_rows(key)
        assert len(row["text"]) == 5000
        results = await env.engine().search(body, _CHUNK_RECIPE)
        (result,) = [
            r
            for r in results
            if isinstance(r.item, Chunk) and str(r.item.id) == str(row["id"])
        ]
        assert Ledger().render(result) == f"[C1] Chunk: {body}"
