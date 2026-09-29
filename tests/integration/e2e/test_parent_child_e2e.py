"""E2E parent-child chunking: extract parents, search children, show parents.

The scenario ingests a Markdown file with a parent-child chunker, a fake extractor that
records the chunks it gets, and a fake embedder, against a real Neo4j. It shows that:

- the extractor sees parent chunks only, and every ``MENTIONED_IN`` edge points at a
  parent,
- parents have no embedding and children have one,
- a chunk search returns children with their parent attached, and the ledger shows the
  parent text once and marks a second child of the same parent,
- ``update()`` with new content closes chunks of both levels, and search returns only
  the new set,
- ``AddResult.chunking`` counts parents and children together under ``parent-child``.

Document keys are unique per run and cleanup removes only what this run created. The
test writes its outcome to ``reports/e2e/parent_child.json``.
"""

import importlib.util
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.chunking import (
    Chunking,
    ParentChildChunker,
    RecursiveChunker,
    SentenceChunker,
)
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact
from tests.integration.e2e.test_chunking_e2e import (
    _CHUNK_RECIPE,
    _cleanup,
    _Env,
    _HashEmbedder,
)


neo4j_missing = importlib.util.find_spec("neo4j") is None

_CHUNKING = Chunking(
    fallback=ParentChildChunker(
        parent=RecursiveChunker(chunk_size=400, tokenizer="character"),
        child=SentenceChunker(chunk_size=90, tokenizer="character"),
    )
)


class _RecordingExtractor(Extractor):
    """Records each chunk it gets and finds the first ``topicN`` word."""

    def __init__(self, label: str) -> None:
        self._label = label
        self.seen: list[Chunk] = []

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return one mention per chunk that holds a topic word."""
        self.seen.append(chunk)
        found = re.search(r"topic\d", chunk.text)
        mentions = []
        if found:
            mentions.append(
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._label,
                    text=found.group(0),
                    char_start=found.start(),
                    char_end=found.end(),
                )
            )
        return ExtractionResult(entities=mentions, relations=[], extractor_name="e2e")


def _markdown(tag: str) -> str:
    sections = []
    for section in range(3):
        sentences = " ".join(
            f"Sentence {i} of {tag} section {section} has topic{(i + section) % 5}."
            for i in range(9)
        )
        sections.append(f"## Section {section}\n\n{sentences}\n")
    return "# Guide\n\n" + "\n".join(sections)


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestParentChildE2E:
    """Parent-child ingestion, search and update through the public API."""

    @pytest.fixture
    async def env(self, tmp_path: Path) -> AsyncGenerator[_Env, None]:
        """Open a store and a folder unique to this test."""
        run = uuid4().hex[:8]
        label = validate_identifier(f"Topic_{run}")
        schema = GraphSchema(
            name="parent_child",
            version="1",
            entities=[EntityType(label=label, description="A topic.")],
            relations=[],
        )
        store = build_graph_store("neo4j")
        root = tmp_path / f"corpus_{run}"
        root.mkdir()
        (root / "guide.md").write_text(_markdown("first"), encoding="utf-8")
        env = _Env(run, store, schema, _HashEmbedder(), root)
        try:
            yield env
        finally:
            try:
                await _cleanup(env)
                await drop_schema_for(store, label)
            finally:
                await store.close()

    async def _levels(self, env: _Env, key: str) -> dict[str, list[str]]:
        rows = await env.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
            "WHERE r.invalid_at IS NULL "
            "RETURN c.id AS id, coalesce(c.level, 0) AS level, "
            "c.embedding IS NOT NULL AS embedded, c.parent_id AS parent_id",
            {"key": key},
        )
        return {
            "parents": sorted(str(r["id"]) for r in rows if r["level"] == 1),
            "children": sorted(str(r["id"]) for r in rows if r["level"] == 0),
            "embedded_parents": [
                str(r["id"]) for r in rows if r["level"] == 1 and r["embedded"]
            ],
            "unembedded_children": [
                str(r["id"]) for r in rows if r["level"] == 0 and not r["embedded"]
            ],
            "orphans": [
                str(r["id"]) for r in rows if r["level"] == 0 and not r["parent_id"]
            ],
        }

    async def test_extract_parents_search_children_show_parents(  # noqa: PLR0915
        self, env: _Env
    ) -> None:
        """Extraction sees parents, search returns children, ledger shows parents."""
        key = str(env.root / "guide.md")
        label = env.schema.entities[0].label
        extractor = _RecordingExtractor(label)
        graph = await Graph.open(
            schema=env.schema,
            graph_store=env.store,
            embedder=env.embedder,
            extractor=extractor,
            chunking=_CHUNKING,
        )
        artifact: dict[str, object] = {}

        added = await graph.add(source=env.root)

        levels = await self._levels(env, key)
        assert levels["parents"] and len(levels["children"]) > len(levels["parents"])
        assert not levels["embedded_parents"]
        assert not levels["unembedded_children"]
        assert not levels["orphans"]
        assert sorted(str(c.id) for c in extractor.seen) == levels["parents"]
        assert all(c.level == 1 for c in extractor.seen)
        assert added.extraction.chunks_processed == len(levels["parents"])
        assert added.chunking.chunks_by_strategy == {
            "parent-child": len(levels["parents"]) + len(levels["children"])
        }
        mention_rows = await env.store.execute_read(
            "MATCH (c:Chunk)-[:MENTIONED_IN]->(e) WHERE e:"
            + label
            + " RETURN DISTINCT c.id AS id"
        )
        mentioned = {str(r["id"]) for r in mention_rows}
        assert mentioned and mentioned <= set(levels["parents"])
        artifact["ingest"] = {
            "parents": len(levels["parents"]),
            "children": len(levels["children"]),
            "extracted_chunks": len(extractor.seen),
            "chunking": added.chunking.model_dump(mode="json", exclude={"matches"}),
        }

        # Search returns children with parents; the ledger shows each parent once.
        results = await env.engine().search("Sentence topic0 section 1", _CHUNK_RECIPE)
        ours = [
            r
            for r in results
            if isinstance(r.item, Chunk) and str(r.item.id) in levels["children"]
        ]
        assert ours
        assert all(
            r.parent is not None and str(r.parent.id) in levels["parents"] for r in ours
        )
        grouped: dict[str, list] = {}
        for result in ours:
            grouped.setdefault(str(result.parent.id), []).append(result)
        siblings = next(v for v in grouped.values() if len(v) >= 2)
        ledger = Ledger()
        first = ledger.render(siblings[0])
        second = ledger.render(siblings[1])
        assert first == f"[C1] Chunk: {siblings[0].parent.text}"
        assert second == f"[C2] Chunk (part of [C1]): {siblings[1].item.text}"
        artifact["search"] = {
            "child_hits_have_parents": True,
            "first_render_is_parent_text": True,
            "second_render": "part of [C1]",
        }

        # Update with new content closes both levels; search shows only the new set.
        (env.root / "guide.md").write_text(_markdown("second"), encoding="utf-8")
        old_ids = set(levels["parents"]) | set(levels["children"])
        changed = await graph.update(key, source=env.root / "guide.md")

        assert changed.no_op is False
        assert changed.chunks_closed == len(old_ids)
        new_levels = await self._levels(env, key)
        new_ids = set(new_levels["parents"]) | set(new_levels["children"])
        assert new_ids and not new_ids & old_ids
        after = await env.engine().search("Sentence topic0 section 1", _CHUNK_RECIPE)
        found = {
            str(r.item.id)
            for r in after
            if isinstance(r.item, Chunk)
            and r.item.document_id == results[0].item.document_id
        }
        assert found and found <= set(new_levels["children"])
        artifact["update"] = {
            "chunks_closed": changed.chunks_closed,
            "old_chunks_current": False,
            "parents_after": len(new_levels["parents"]),
            "children_after": len(new_levels["children"]),
        }

        write_artifact("parent_child", artifact)
