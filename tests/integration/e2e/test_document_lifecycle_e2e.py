"""End-to-end tests for the document lifecycle through the public Graph API.

One user story runs against a real Neo4j: add two documents, add one again,
update it, then delete the other. After each step the tests read the graph
and search it with SearchEngine, and check that closed versions no longer
appear in retrieval and that shared entities survive. Another group of tests
interrupts an add with an extractor error or an embedder error, then runs the
add again and checks that the graph ends complete with no duplicates.

Every label, document key, and text carries a per-run id, so the tests can
share a database with other tests. Cleanup removes only what one run created.
Each test writes a JSON artifact with stable names and counts under
``reports/e2e/``.
"""

import hashlib
import importlib.util
import unicodedata
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.corpus.types import ErrorPolicy
from agrag.retrieval.recipes import ENTITY, Recipe
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


neo4j_missing = importlib.util.find_spec("neo4j") is None

_CHUNK_RECIPE = Recipe(methods=["chunk"], limit=200)

# Every keyword the fake embedder and extractor know, with its entity kind.
_KEYWORDS: dict[str, tuple[str, str]] = {
    "aspirin": ("drug", "Aspirin"),
    "ibuprofen": ("drug", "Ibuprofen"),
    "naproxen": ("drug", "Naproxen"),
    "headache": ("condition", "Headache"),
    "fever": ("condition", "Fever"),
    "inflammation": ("condition", "Inflammation"),
}

# Four dimensions match the shared Chunk vector index other tests create.
_AXES: dict[str, tuple[float, float, float, float]] = {
    "aspirin": (1.0, 0.0, 0.0, 0.0),
    "ibuprofen": (0.0, 1.0, 0.0, 0.0),
    "naproxen": (0.0, 0.0, 1.0, 0.0),
    "headache": (0.0, 0.0, 0.0, 1.0),
    "fever": (0.5, 0.5, 0.0, 0.0),
    "inflammation": (0.0, 0.0, 0.5, 0.5),
}


class _KeywordEmbedder(Embedder):
    """Embedder whose vectors follow the known keywords in the text."""

    model = "keyword"

    def __init__(self) -> None:
        """Start with no poison marker."""
        self.fail_marker: str | None = None

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Sum the axis of each keyword found, plus a small constant."""
        vectors: list[list[float]] = []
        for text in texts:
            if self.fail_marker is not None and self.fail_marker in text:
                raise RuntimeError("embedder unavailable")
            lowered = text.lower()
            vector = [0.01] * 4
            for keyword, axis in _AXES.items():
                if keyword in lowered:
                    vector = [v + a for v, a in zip(vector, axis, strict=True)]
            vectors.append(vector)
        return vectors


class _KeywordExtractor(Extractor):
    """Extractor that finds the known keywords and can fail on a marker."""

    def __init__(self, drug_label: str, condition_label: str) -> None:
        """Remember the labels to emit and start with no poison marker."""
        self._labels = {"drug": drug_label, "condition": condition_label}
        self.fail_marker: str | None = None

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return one mention per keyword found in the chunk."""
        if self.fail_marker is not None and self.fail_marker in chunk.text:
            raise RuntimeError("extractor unavailable")
        lowered = chunk.text.lower()
        mentions: list[ExtractedEntity] = []
        for keyword, (kind, name) in _KEYWORDS.items():
            start = lowered.find(keyword)
            if start < 0:
                continue
            mentions.append(
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._labels[kind],
                    text=name,
                    char_start=start,
                    char_end=start + len(keyword),
                )
            )
        return ExtractionResult(entities=mentions, relations=[], extractor_name="e2e")


def _topics(text: str) -> str:
    """Name the known keywords in a text, sorted and joined with plus signs."""
    lowered = text.lower()
    return "+".join(sorted(k for k in _KEYWORDS if k in lowered))


def _content_hash(text: str) -> str:
    """Hash text the way Graph.update() does."""
    return hashlib.sha256(
        unicodedata.normalize("NFKC", text).encode("utf-8")
    ).hexdigest()


def _document(key: str, text: str) -> Document:
    """Build a prose Document with an explicit stable key."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="lifecycle",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_content_hash(normalized),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
    )


@dataclass
class _Env:
    """Everything one test needs, all scoped to one run id."""

    run: str
    store: GraphStore
    graph: Graph
    engine: SearchEngine
    embedder: _KeywordEmbedder
    extractor: _KeywordExtractor
    drug_label: str
    condition_label: str

    def key(self, name: str) -> str:
        """Return the document key for a short name."""
        return f"lifecycle://{self.run}/{name}"

    def text(self, body: str) -> str:
        """Tag a body with the run id so its chunks are recognizable."""
        return f"{body} Reference {self.run}."

    async def entity_names(self) -> list[str]:
        """Return the sorted live entity names of this run's labels."""
        rows = await self.store.execute_read(
            "MATCH (n) WHERE ($drug IN labels(n) OR $condition IN labels(n)) "
            "AND n.merged_into IS NULL RETURN n.name AS name",
            {"drug": self.drug_label, "condition": self.condition_label},
        )
        return sorted(str(row["name"]) for row in rows)

    async def supported_entities(self, name: str) -> list[str]:
        """Return entities mentioned by the open chunks of one document."""
        rows = await self.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk)"
            "-[:MENTIONED_IN]->(e) WHERE r.invalid_at IS NULL "
            "RETURN DISTINCT e.name AS name",
            {"key": self.key(name)},
        )
        return sorted(str(row["name"]) for row in rows)

    async def open_topics(self, name: str) -> list[str]:
        """Return the topics of each open chunk of one document."""
        rows = await self.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
            "WHERE r.invalid_at IS NULL RETURN c.text AS text",
            {"key": self.key(name)},
        )
        return sorted(_topics(str(row["text"])) for row in rows)

    async def edge_counts(self, name: str) -> dict[str, int]:
        """Return total and open PART_OF edge counts of one document."""
        rows = await self.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(:Chunk) "
            "RETURN count(r) AS total, "
            "count(CASE WHEN r.invalid_at IS NULL THEN 1 END) AS open",
            {"key": self.key(name)},
        )
        return {"total": int(rows[0]["total"]), "open": int(rows[0]["open"])}

    async def count(self, label: str, where: str, params: dict[str, str]) -> int:
        """Count nodes of a label that match a filter."""
        rows = await self.store.execute_read(
            f"MATCH (n:{label}) WHERE {where} RETURN count(n) AS n", params
        )
        return int(rows[0]["n"])

    async def chunk_nodes(self) -> int:
        """Count every Chunk node of this run, open or closed."""
        return await self.count("Chunk", "n.text CONTAINS $run", {"run": self.run})

    async def document_nodes(self) -> int:
        """Count every Document node of this run."""
        return await self.count(
            "Document", "n.document_key STARTS WITH $prefix", {"prefix": self.key("")}
        )

    async def chunk_hits(self, query: str) -> list[str]:
        """Return topics of this run's chunks in search rank order."""
        results = await self.engine.search(query, _CHUNK_RECIPE)
        return [
            _topics(result.item.text)
            for result in results
            if isinstance(result.item, Chunk) and self.run in result.item.text
        ]

    async def entity_hits(self, query: str) -> list[str]:
        """Return entity names of this run's labels in search rank order."""
        results = await self.engine.search(query, ENTITY)
        return [
            str(result.item.name)
            for result in results
            if getattr(result.item, "label", None)
            in (self.drug_label, self.condition_label)
        ]

    async def snapshot(self) -> dict[str, Any]:
        """Capture the graph state that add, update, and delete change."""
        docs = ("a", "b", "c", "d")
        return {
            "entities": await self.entity_names(),
            "chunk_nodes": await self.chunk_nodes(),
            "document_nodes": await self.document_nodes(),
            "edges": {n: await self.edge_counts(n) for n in docs},
            "open_topics": {n: await self.open_topics(n) for n in docs},
            "supported": {n: await self.supported_entities(n) for n in docs},
        }


async def _cleanup(env: _Env) -> None:
    """Remove only the nodes this run created."""
    store = env.store
    prefix = env.key("")
    for label in (env.drug_label, env.condition_label):
        await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        await store.execute_write(
            "MATCH (a:_AgragMergeAlias) WHERE a.merge_key STARTS WITH $prefix "
            "DETACH DELETE a",
            {"prefix": f"{label}:"},
        )
    await store.execute_write(
        "MATCH (c:Chunk) WHERE c.text CONTAINS $run DETACH DELETE c",
        {"run": env.run},
    )
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix DETACH DELETE d",
        {"prefix": prefix},
    )
    await store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        {"prefix": prefix},
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestDocumentLifecycleE2E:
    """Add, update, delete, and interrupted add through Graph and SearchEngine."""

    @pytest.fixture
    async def env(self) -> AsyncGenerator[_Env, None]:
        """Open a graph on labels unique to this test."""
        run = uuid4().hex[:8]
        drug_label = validate_identifier(f"Drug_{run}")
        condition_label = validate_identifier(f"Condition_{run}")
        schema = GraphSchema(
            name="lifecycle",
            version="1",
            entities=[
                EntityType(label=drug_label, description="A medication."),
                EntityType(label=condition_label, description="A condition."),
            ],
            relations=[],
        )
        store = build_graph_store("neo4j")
        embedder = _KeywordEmbedder()
        extractor = _KeywordExtractor(drug_label, condition_label)
        graph = await Graph.open(
            schema=schema, graph_store=store, embedder=embedder, extractor=extractor
        )
        engine = SearchEngine(
            graph_store=store,
            embedder=embedder,
            settings=RetrievalSettings(entity_top_k=50, chunk_top_k=200),
            graph_schema=schema,
        )
        env = _Env(
            run=run,
            store=store,
            graph=graph,
            engine=engine,
            embedder=embedder,
            extractor=extractor,
            drug_label=drug_label,
            condition_label=condition_label,
        )
        try:
            yield env
        finally:
            try:
                await _cleanup(env)
                await drop_schema_for(store, drug_label, condition_label)
            finally:
                await store.close()

    async def test_add_update_delete_keeps_retrieval_current(  # noqa: PLR0915
        self, env: _Env
    ) -> None:
        """Retrieval and entities follow each add, update, and delete."""
        key_a, key_b = env.key("a"), env.key("b")
        text_a1 = env.text("Aspirin relieves headache.")
        text_b1 = env.text("Ibuprofen relieves headache and fever.")
        text_a2 = env.text("Naproxen relieves headache and inflammation.")
        artifact: dict[str, object] = {}

        # Step 1: add two documents that share the headache entity.
        await env.graph.add(
            documents=[_document(key_a, text_a1), _document(key_b, text_b1)]
        )
        added = await env.snapshot()
        assert added["entities"] == ["Aspirin", "Fever", "Headache", "Ibuprofen"]
        assert added["supported"] == {
            "a": ["Aspirin", "Headache"],
            "b": ["Fever", "Headache", "Ibuprofen"],
            "c": [],
            "d": [],
        }
        assert (await env.chunk_hits("aspirin"))[0] == "aspirin+headache"
        assert (await env.chunk_hits("ibuprofen fever"))[
            0
        ] == "fever+headache+ibuprofen"
        assert (await env.entity_hits("Aspirin"))[0] == "Aspirin"
        artifact["1_added"] = added

        # Step 2: add one document again with no change. add() has no
        # unchanged flag, so the graph must stay the same, and update()
        # with the same text must report a no-op.
        await env.graph.add(documents=[_document(key_a, text_a1)])
        assert await env.snapshot() == added
        same = await env.graph.update(key_a, text=text_a1)
        assert same.no_op is True
        assert same.chunks_closed == 0
        assert same.add_result is None
        assert same.previous_content_hash == same.new_content_hash
        assert await env.snapshot() == added
        artifact["2_readd_unchanged"] = {
            "graph_unchanged": True,
            "update_no_op": same.no_op,
        }

        # Step 3: change document a. The old version closes, entities only the
        # old text supported go away, and shared entities stay.
        updated = await env.graph.update(key_a, text=text_a2)
        assert updated.no_op is False
        assert updated.chunks_closed == 1
        assert updated.previous_content_hash == _content_hash(text_a1)
        assert updated.new_content_hash == _content_hash(text_a2)
        assert updated.add_result is not None
        after_update = await env.snapshot()
        assert after_update["entities"] == [
            "Fever",
            "Headache",
            "Ibuprofen",
            "Inflammation",
            "Naproxen",
        ]
        assert after_update["open_topics"] == {
            "a": ["headache+inflammation+naproxen"],
            "b": ["fever+headache+ibuprofen"],
            "c": [],
            "d": [],
        }
        assert after_update["edges"]["a"] == {"total": 2, "open": 1}
        # The closed chunk stays as history; only open edges feed retrieval.
        assert after_update["chunk_nodes"] == 3
        hits_new = await env.chunk_hits("naproxen")
        assert hits_new[0] == "headache+inflammation+naproxen"
        hits_old = await env.chunk_hits("aspirin")
        assert "aspirin+headache" not in hits_old
        assert "Aspirin" not in await env.entity_hits("Aspirin")
        assert (await env.entity_hits("Naproxen"))[0] == "Naproxen"
        artifact["3_updated"] = after_update
        artifact["3_search"] = {
            "naproxen_chunks": hits_new,
            "aspirin_chunks": hits_old,
        }

        # Step 4: delete document b. Its own entities go, and headache stays
        # because the new version of document a still mentions it.
        deleted = await env.graph.delete_document(key_b)
        assert deleted.no_op is False
        assert deleted.chunks_closed == 1
        assert deleted.new_content_hash is None
        after_delete = await env.snapshot()
        assert after_delete["entities"] == ["Headache", "Inflammation", "Naproxen"]
        assert after_delete["open_topics"]["b"] == []
        assert after_delete["supported"]["a"] == [
            "Headache",
            "Inflammation",
            "Naproxen",
        ]
        hits_deleted = await env.chunk_hits("ibuprofen fever")
        assert "fever+headache+ibuprofen" not in hits_deleted
        assert "Ibuprofen" not in await env.entity_hits("Ibuprofen")
        assert (await env.chunk_hits("headache"))[0] == "headache+inflammation+naproxen"
        unknown = await env.graph.delete_document(env.key("never_added"))
        assert unknown.no_op is True
        artifact["4_deleted"] = after_delete
        artifact["4_search"] = {"ibuprofen_chunks": hits_deleted}

        written = write_artifact("document_lifecycle", artifact)
        assert written == artifact

    async def test_update_with_same_length_text_replaces_content(
        self, env: _Env
    ) -> None:
        """An update whose new text has the same length still swaps the content."""
        key = env.key("a")
        before = env.text("Ibuprofen relieves headache.")
        after = env.text("Naproxen. relieves headache.")
        assert len(before) == len(after)
        await env.graph.add(documents=[_document(key, before)])

        updated = await env.graph.update(key, text=after)

        assert updated.no_op is False
        assert updated.chunks_closed == 1
        state = await env.snapshot()
        assert state["open_topics"] == {
            "a": ["headache+naproxen"],
            "b": [],
            "c": [],
            "d": [],
        }
        assert state["entities"] == ["Headache", "Naproxen"]
        assert "headache+ibuprofen" not in await env.chunk_hits("ibuprofen")
        assert (await env.chunk_hits("naproxen"))[0] == "headache+naproxen"
        artifact = write_artifact("document_lifecycle_same_length", state)
        assert artifact["entities"] == ["Headache", "Naproxen"]

    async def test_interrupted_adds_recover_on_rerun(  # noqa: PLR0915
        self, env: _Env
    ) -> None:
        """Extractor and embedder failures leave no partial state and heal on rerun."""
        artifact: dict[str, object] = {}
        good = env.text("Aspirin relieves headache.")
        bad = env.text("Ibuprofen relieves fever. Explode.")

        # Failure 1: the extractor raises under the default policy. Extraction
        # runs before any write, so the whole call leaves nothing behind.
        env.extractor.fail_marker = "Explode"
        with pytest.raises(RuntimeError, match="extractor unavailable"):
            await env.graph.add(
                documents=[_document(env.key("c"), good), _document(env.key("d"), bad)]
            )
        assert await env.document_nodes() == 0
        assert await env.chunk_nodes() == 0
        assert await env.entity_names() == []
        env.extractor.fail_marker = None
        await env.graph.add(
            documents=[_document(env.key("c"), good), _document(env.key("d"), bad)]
        )
        complete = await env.snapshot()
        assert complete["entities"] == ["Aspirin", "Fever", "Headache", "Ibuprofen"]
        assert complete["edges"]["c"] == {"total": 1, "open": 1}
        assert complete["edges"]["d"] == {"total": 1, "open": 1}
        assert complete["chunk_nodes"] == 2
        artifact["1_extractor_raise_then_rerun"] = complete
        await _cleanup(env)

        # Failure 2: the extractor fails on one chunk under the skip policy.
        # The call reports the failure and stores that chunk with no
        # entities; a rerun fills them in without duplicating anything.
        env.extractor.fail_marker = "Explode"
        skipped = await env.graph.add(
            documents=[_document(env.key("c"), good), _document(env.key("d"), bad)],
            error_policy=ErrorPolicy.SKIP,
        )
        assert skipped.extraction.failures_total == 1
        assert skipped.extraction.failures[0].error_type == "RuntimeError"
        assert skipped.extraction.failures[0].error_message == "extractor unavailable"
        partial = await env.snapshot()
        assert partial["entities"] == ["Aspirin", "Headache"]
        assert partial["supported"]["d"] == []
        env.extractor.fail_marker = None
        rerun = await env.graph.add(
            documents=[_document(env.key("c"), good), _document(env.key("d"), bad)],
            error_policy=ErrorPolicy.SKIP,
        )
        assert rerun.extraction.failures_total == 0
        healed = await env.snapshot()
        assert healed == complete
        artifact["2_extractor_skip"] = {
            "failures_total": skipped.extraction.failures_total,
            "failure_type": skipped.extraction.failures[0].error_type,
            "entities_after_failure": partial["entities"],
            "entities_after_rerun": healed["entities"],
            "rerun_equals_clean_run": healed == complete,
        }
        await _cleanup(env)

        # Failure 3: the embedder fails while one document is being written.
        # That document's job rolls back in full and the other document,
        # already committed, stays; the rerun finishes the missing one.
        env.embedder.fail_marker = "Explode"
        with pytest.raises(RuntimeError, match="embedder unavailable"):
            await env.graph.add(
                documents=[_document(env.key("c"), good), _document(env.key("d"), bad)]
            )
        after_failure = await env.snapshot()
        assert after_failure["edges"]["d"] == {"total": 0, "open": 0}
        assert after_failure["supported"]["d"] == []
        assert after_failure["chunk_nodes"] == 1
        assert await env.chunk_hits("fever") == ["aspirin+headache"]
        assert after_failure["entities"] == ["Aspirin", "Headache"]
        env.embedder.fail_marker = None
        await env.graph.add(
            documents=[_document(env.key("c"), good), _document(env.key("d"), bad)]
        )
        final = await env.snapshot()
        assert final == complete
        assert (await env.chunk_hits("ibuprofen"))[0] == "fever+ibuprofen"
        artifact["3_embedder_failure"] = {
            "entities_after_failure": after_failure["entities"],
            "chunk_nodes_after_failure": after_failure["chunk_nodes"],
            "rerun_equals_clean_run": final == complete,
        }

        written = write_artifact("document_lifecycle_interrupted", artifact)
        assert written == artifact
