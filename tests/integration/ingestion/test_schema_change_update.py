"""Integration tests for update() after a schema or extraction change.

update() picks one of three paths from the stamps on the stored Document and
Chunk nodes. A schema structure change writes new chunks. A change that only
affects extraction re-extracts in place and keeps the chunk ids and their
embeddings. A deleted document comes back on update, and a failed update
leaves the committed version untouched.

Every label and document key carries a per-run id so the tests can share a
database with other tests. Cleanup removes only what one run created. Each
test writes a JSON artifact under ``reports/e2e/``.
"""

import hashlib
import importlib.util
import re
import unicodedata
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.schema_fingerprint import schema_fingerprint
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.settings import ExtractionSettings
from agrag.loaders.common import text_sections
from agrag.loaders.types import ErrorPolicy
from agrag.retrieval.recipes import Recipe
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


neo4j_missing = importlib.util.find_spec("neo4j") is None

_BODY = "Ada met Bob in Paris."
_CHUNK_RECIPE = Recipe(methods=["chunk"], limit=200)

# Four dimensions match the shared Chunk vector index other tests create.
_AXES: dict[str, tuple[float, float, float, float]] = {
    "ada": (1.0, 0.0, 0.0, 0.0),
    "bob": (0.0, 1.0, 0.0, 0.0),
    "paris": (0.0, 0.0, 1.0, 0.0),
}


class _RecordingEmbedder(Embedder):
    """Embedder that records every text it is asked to embed."""

    model = "recording"

    def __init__(self) -> None:
        """Start with no recorded texts."""
        self.texts: list[str] = []

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Record the texts and return vectors that follow the known keywords."""
        self.texts.extend(texts)
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vector = [0.01] * 4
            for keyword, axis in _AXES.items():
                if keyword in lowered:
                    vector = [v + a for v, a in zip(vector, axis, strict=True)]
            vectors.append(vector)
        return vectors


class _KeywordExtractor(Extractor):
    """Extractor that emits one mention per keyword and relations between them."""

    def __init__(
        self,
        mentions: dict[str, tuple[str, str]],
        relations: Sequence[tuple[str, str, str]] = (),
    ) -> None:
        """Map each keyword to the (label, name) it produces.

        Args:
            mentions: Lowercase keyword to the entity label and name it yields.
            relations: (relation label, source keyword, target keyword) triples.
                A relation is emitted for a chunk where both keywords occur.
        """
        self._mentions = mentions
        self._relations = tuple(relations)
        self.fail_marker: str | None = None

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return one mention per keyword found as a whole word in the chunk."""
        if self.fail_marker is not None and self.fail_marker in chunk.text:
            raise RuntimeError("extractor unavailable")
        found: list[ExtractedEntity] = []
        index_of: dict[str, int] = {}
        for keyword, (label, name) in self._mentions.items():
            match = re.search(rf"\b{keyword}\b", chunk.text, re.IGNORECASE)
            if match is None:
                continue
            index_of[keyword] = len(found)
            found.append(
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=label,
                    text=name,
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )
        relations = [
            ExtractedRelation(
                chunk_id=chunk.id,
                label=label,
                source_index=index_of[source],
                target_index=index_of[target],
            )
            for label, source, target in self._relations
            if source in index_of and target in index_of
        ]
        return ExtractionResult(
            entities=found, relations=relations, extractor_name="keyword"
        )


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
        title="schema change",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_content_hash(normalized),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
        sections=text_sections(normalized),
    )


@dataclass
class _Env:
    """Everything one test needs, all scoped to one run id."""

    run: str
    store: GraphStore
    person: str
    place: str
    knows: str
    mentors: str

    def key(self, name: str) -> str:
        """Return the document key for a short name."""
        return f"schema_change://{self.run}/{name}"

    def text(self, body: str) -> str:
        """Tag a body with the run id so its chunks are recognizable."""
        return f"{body} Reference {self.run}."


def _schema(
    env: _Env,
    *,
    person_description: str = "A person.",
    with_place: bool = True,
    with_relations: bool = False,
) -> GraphSchema:
    """Build the schema of one run, with or without the place and relations."""
    entities = [EntityType(label=env.person, description=person_description)]
    if with_place:
        entities.append(EntityType(label=env.place, description="A place."))
    relations: list[RelationType] = []
    if with_relations:
        relations = [
            RelationType(
                label=env.knows,
                description="A person knows another person.",
                patterns=[(env.person, env.person)],
            ),
            RelationType(
                label=env.mentors,
                description="A person mentors another person.",
                patterns=[(env.person, env.person)],
            ),
        ]
    return GraphSchema(
        name="schema_change", version="1", entities=entities, relations=relations
    )


def _people(env: _Env) -> dict[str, tuple[str, str]]:
    """Return the keyword mentions that yield only the two people."""
    return {"ada": (env.person, "Ada"), "bob": (env.person, "Bob")}


def _full(env: _Env) -> dict[str, tuple[str, str]]:
    """Return the keyword mentions that yield the two people and the place."""
    return {**_people(env), "paris": (env.place, "Paris")}


def _knows(env: _Env) -> tuple[str, str, str]:
    """Return the relation Ada knows Bob, which both runs extract."""
    return (env.knows, "ada", "bob")


def _mentors(env: _Env) -> tuple[str, str, str]:
    """Return the relation Ada mentors Bob, which only the first run extracts."""
    return (env.mentors, "ada", "bob")


async def _relations(store: GraphStore, rel_type: str) -> list[dict[str, Any]]:
    """Return the endpoints and sorted chunk ids of each relation of one type."""
    rows = await store.execute_read(
        f"MATCH (a)-[r:{rel_type}]->(b) "
        "RETURN a.name AS source, b.name AS target, "
        "r.source_chunk_ids AS chunk_ids",
    )
    return sorted(
        (
            {
                "source": str(row["source"]),
                "target": str(row["target"]),
                "chunk_ids": sorted(str(cid) for cid in row["chunk_ids"] or []),
            }
            for row in rows
        ),
        key=lambda relation: (relation["source"], relation["target"]),
    )


async def _open(
    env: _Env,
    schema: GraphSchema,
    extractor: _KeywordExtractor,
    embedder: _RecordingEmbedder,
    *,
    extraction_settings: ExtractionSettings | None = None,
) -> Graph:
    """Open a graph on this run's store with local-only extraction settings."""
    settings = (
        extraction_settings
        if extraction_settings is not None
        else ExtractionSettings(mode="gliner")
    )
    return await Graph.open(
        schema=schema,
        graph_store=env.store,
        embedder=embedder,
        extractor=extractor,
        extraction_settings=settings,
    )


async def _document_row(store: GraphStore, key: str) -> dict[str, Any]:
    """Return the content hash and both fingerprints of a Document node."""
    rows = await store.execute_read(
        "MATCH (d:Document {document_key: $key}) "
        "RETURN d.current_content_hash AS content_hash, "
        "d.schema_fingerprint AS schema_fingerprint, "
        "d.extraction_fingerprint AS extraction_fingerprint",
        {"key": key},
    )
    return dict(rows[0])


async def _open_chunks(store: GraphStore, key: str) -> list[dict[str, Any]]:
    """Return the id and stamps of each open chunk of one document."""
    rows = await store.execute_read(
        "MATCH (:Document {document_key: $key})-[r:HAS_PART]->(c:Chunk) "
        "WHERE r.invalid_at IS NULL "
        "RETURN c.id AS id, c.schema_fingerprint AS schema_fingerprint, "
        "c.extraction_fingerprint AS extraction_fingerprint",
        {"key": key},
    )
    return [dict(row) for row in rows]


def _chunk_ids(rows: list[dict[str, Any]]) -> list[str]:
    """Return the sorted chunk ids of rows from ``_open_chunks``."""
    return sorted(str(row["id"]) for row in rows)


async def _entity_names(store: GraphStore, label: str) -> list[str]:
    """Return the sorted names of the entities that carry one label."""
    rows = await store.execute_read(
        "MATCH (n) WHERE $label IN labels(n) RETURN n.name AS name",
        {"label": label},
    )
    return sorted(str(row["name"]) for row in rows)


async def _mentioned_names(store: GraphStore, chunk_ids: list[str]) -> list[str]:
    """Return the sorted names of every entity the given chunks mention."""
    rows = await store.execute_read(
        "MATCH (c:Chunk)-[:MENTIONED_IN]->(e) WHERE c.id IN $ids "
        "RETURN DISTINCT e.name AS name",
        {"ids": chunk_ids},
    )
    return sorted(str(row["name"]) for row in rows)


async def _search_chunks(
    env: _Env, embedder: _RecordingEmbedder, schema: GraphSchema, query: str
) -> list[str]:
    """Return the texts of this run's open chunks that a search finds."""
    engine = SearchEngine(
        graph_store=env.store,
        embedder=embedder,
        settings=RetrievalSettings(entity_top_k=50, chunk_top_k=200),
        graph_schema=schema,
    )
    results = await engine.search(query, _CHUNK_RECIPE)
    return [
        result.item.text
        for result in results
        if isinstance(result.item, Chunk) and env.run in result.item.text
    ]


async def _cleanup(env: _Env) -> None:
    """Remove only the nodes this run created."""
    store = env.store
    for rel_type in (env.knows, env.mentors):
        await store.execute_write(f"MATCH ()-[r:{rel_type}]->() DELETE r")
    for label in (env.person, env.place):
        await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        await store.execute_write(
            "MATCH (a:_MergeAlias) WHERE a.merge_key STARTS WITH $prefix "
            "DETACH DELETE a",
            {"prefix": f"{label}:"},
        )
    await store.execute_write(
        "MATCH (c:Chunk) WHERE c.text CONTAINS $run DETACH DELETE c",
        {"run": env.run},
    )
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix DETACH DELETE d",
        {"prefix": env.key("")},
    )
    await store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        {"prefix": env.key("")},
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestSchemaChangeUpdate:
    """update() after a schema, extraction, delete, or failed-update change."""

    @pytest.fixture
    async def env(self) -> AsyncGenerator[_Env, None]:
        """Connect a store and give it labels unique to this test."""
        run = uuid4().hex[:8]
        store = build_graph_store("neo4j")
        await store.connect()
        env = _Env(
            run=run,
            store=store,
            person=validate_identifier(f"Person_{run}"),
            place=validate_identifier(f"Place_{run}"),
            knows=validate_identifier(f"Knows_{run}"),
            mentors=validate_identifier(f"Mentors_{run}"),
        )
        try:
            yield env
        finally:
            try:
                await _cleanup(env)
                await drop_schema_for(
                    store, env.person, env.place, env.knows, env.mentors
                )
            finally:
                await store.close()

    async def test_structure_change_with_same_text_writes_new_chunks(
        self, env: _Env
    ) -> None:
        """A changed schema structure replaces the chunks and drops old entities."""
        key = env.key("doc")
        text = env.text(_BODY)
        first = await _open(
            env, _schema(env), _KeywordExtractor(_full(env)), _RecordingEmbedder()
        )
        await first.add(documents=[_document(key, text)])
        old_chunk_ids = _chunk_ids(await _open_chunks(env.store, key))

        second_schema = _schema(env, with_place=False)
        second_embedder = _RecordingEmbedder()
        second = await _open(
            env, second_schema, _KeywordExtractor(_people(env)), second_embedder
        )
        result = await second.update(key, text=text)

        assert result.no_op is False
        open_rows = await _open_chunks(env.store, key)
        new_chunk_ids = _chunk_ids(open_rows)
        assert len(new_chunk_ids) == 1
        assert set(new_chunk_ids).isdisjoint(old_chunk_ids)
        chunks_embedded = any(_BODY in recorded for recorded in second_embedder.texts)
        assert chunks_embedded
        expected = schema_fingerprint(second_schema)
        document = await _document_row(env.store, key)
        assert document["schema_fingerprint"] == expected
        assert {row["schema_fingerprint"] for row in open_rows} == {expected}
        assert await _entity_names(env.store, env.place) == []
        assert await _entity_names(env.store, env.person) == ["Ada", "Bob"]
        assert await _mentioned_names(env.store, new_chunk_ids) == ["Ada", "Bob"]

        again = await second.update(key, text=text)

        assert again.no_op is True
        artifact = {
            "no_op": result.no_op,
            "person_entities": await _entity_names(env.store, env.person),
            "place_entities": await _entity_names(env.store, env.place),
            "open_chunks": len(new_chunk_ids),
            "chunk_ids_replaced": True,
            "chunks_embedded": chunks_embedded,
            "repeat_no_op": again.no_op,
        }
        written = write_artifact("schema_change_structure", artifact)
        assert written == artifact

    async def test_description_change_re_extracts_in_place(self, env: _Env) -> None:
        """A changed description keeps the chunks and re-runs extraction only."""
        key = env.key("doc")
        text = env.text(_BODY)
        first = await _open(
            env,
            _schema(env, with_relations=True),
            _KeywordExtractor(_full(env), [_knows(env), _mentors(env)]),
            _RecordingEmbedder(),
        )
        await first.add(documents=[_document(key, text)])
        before_rows = await _open_chunks(env.store, key)
        before = await _document_row(env.store, key)

        second_embedder = _RecordingEmbedder()
        second = await _open(
            env,
            _schema(env, person_description="A human being.", with_relations=True),
            _KeywordExtractor(_people(env), [_knows(env)]),
            second_embedder,
        )
        result = await second.update(key, text=text)

        assert result.no_op is False
        after_rows = await _open_chunks(env.store, key)
        after = await _document_row(env.store, key)
        chunks_embedded = any(_BODY in recorded for recorded in second_embedder.texts)
        assert _chunk_ids(after_rows) == _chunk_ids(before_rows)
        assert not chunks_embedded
        assert after["schema_fingerprint"] == before["schema_fingerprint"]
        assert after["extraction_fingerprint"]
        assert after["extraction_fingerprint"] != before["extraction_fingerprint"]
        stamped = {row["extraction_fingerprint"] for row in after_rows}
        assert stamped == {after["extraction_fingerprint"]}
        assert await _entity_names(env.store, env.place) == []
        assert await _entity_names(env.store, env.person) == ["Ada", "Bob"]
        chunk_ids = _chunk_ids(after_rows)
        assert await _mentioned_names(env.store, chunk_ids) == ["Ada", "Bob"]
        knows = await _relations(env.store, env.knows)
        assert knows == [{"source": "Ada", "target": "Bob", "chunk_ids": chunk_ids}]
        assert await _relations(env.store, env.mentors) == []

        again = await second.update(key, text=text)

        assert again.no_op is True
        artifact = {
            "no_op": result.no_op,
            "entities": await _entity_names(env.store, env.person),
            "relations": knows,
            "chunk_ids_kept": _chunk_ids(after_rows) == _chunk_ids(before_rows),
            "chunks_embedded": chunks_embedded,
            "schema_fingerprint_kept": True,
            "extraction_fingerprint_changed": True,
            "repeat_no_op": again.no_op,
        }
        written = write_artifact("schema_change_description", artifact)
        assert written == artifact

    async def test_extraction_settings_change_re_extracts_in_place(
        self, env: _Env
    ) -> None:
        """A changed extraction setting keeps the chunks, like a description."""
        key = env.key("doc")
        text = env.text(_BODY)
        schema = _schema(env, with_relations=True)
        first = await _open(
            env,
            schema,
            _KeywordExtractor(_full(env), [_knows(env), _mentors(env)]),
            _RecordingEmbedder(),
            extraction_settings=ExtractionSettings(mode="gliner", entity_threshold=0.5),
        )
        await first.add(documents=[_document(key, text)])
        before_rows = await _open_chunks(env.store, key)
        before = await _document_row(env.store, key)

        second_embedder = _RecordingEmbedder()
        without_paris = {
            keyword: mention
            for keyword, mention in _full(env).items()
            if keyword != "paris"
        }
        second = await _open(
            env,
            schema,
            _KeywordExtractor(without_paris, [_knows(env)]),
            second_embedder,
            extraction_settings=ExtractionSettings(mode="gliner", entity_threshold=0.9),
        )
        result = await second.update(key, text=text)

        assert result.no_op is False
        after_rows = await _open_chunks(env.store, key)
        after = await _document_row(env.store, key)
        chunks_embedded = any(_BODY in recorded for recorded in second_embedder.texts)
        assert _chunk_ids(after_rows) == _chunk_ids(before_rows)
        assert not chunks_embedded
        assert await _entity_names(env.store, env.place) == []
        assert await _entity_names(env.store, env.person) == ["Ada", "Bob"]
        assert after["schema_fingerprint"] == before["schema_fingerprint"]
        assert after["extraction_fingerprint"] != before["extraction_fingerprint"]
        stamped = {row["extraction_fingerprint"] for row in after_rows}
        assert stamped == {after["extraction_fingerprint"]}
        knows = await _relations(env.store, env.knows)
        assert knows == [
            {"source": "Ada", "target": "Bob", "chunk_ids": _chunk_ids(after_rows)}
        ]
        assert await _relations(env.store, env.mentors) == []

        again = await second.update(key, text=text)

        assert again.no_op is True
        artifact = {
            "no_op": result.no_op,
            "relations": knows,
            "chunk_ids_kept": _chunk_ids(after_rows) == _chunk_ids(before_rows),
            "chunks_embedded": chunks_embedded,
            "schema_fingerprint_kept": True,
            "extraction_fingerprint_changed": True,
            "repeat_no_op": again.no_op,
        }
        written = write_artifact("schema_change_extraction_settings", artifact)
        assert written == artifact

    async def test_in_place_update_keeps_relation_evidenced_by_other_document(
        self, env: _Env
    ) -> None:
        """A relation another document evidences survives an in-place update."""
        key = env.key("doc")
        other_key = env.key("other")
        text = env.text(_BODY)
        other_text = env.text("Ada and Bob met again.")
        first = await _open(
            env,
            _schema(env, with_relations=True),
            _KeywordExtractor(_full(env), [_knows(env), _mentors(env)]),
            _RecordingEmbedder(),
        )
        await first.add(
            documents=[_document(key, text), _document(other_key, other_text)]
        )
        own_chunk_ids = _chunk_ids(await _open_chunks(env.store, key))
        other_chunk_ids = _chunk_ids(await _open_chunks(env.store, other_key))

        second = await _open(
            env,
            _schema(env, person_description="A human being.", with_relations=True),
            _KeywordExtractor(_people(env), [_knows(env)]),
            _RecordingEmbedder(),
        )
        result = await second.update(key, text=text)

        assert result.no_op is False
        knows = await _relations(env.store, env.knows)
        assert knows == [
            {
                "source": "Ada",
                "target": "Bob",
                "chunk_ids": sorted([*own_chunk_ids, *other_chunk_ids]),
            }
        ]
        mentors = await _relations(env.store, env.mentors)
        assert mentors == [
            {"source": "Ada", "target": "Bob", "chunk_ids": sorted(other_chunk_ids)}
        ]
        assert _chunk_ids(await _open_chunks(env.store, key)) == own_chunk_ids
        artifact = {
            "relations": knows,
            "relations_only_the_other_document_evidences": mentors,
            "own_chunk_count": len(own_chunk_ids),
            "other_chunk_count": len(other_chunk_ids),
        }
        written = write_artifact("schema_change_shared_relation", artifact)
        assert written == artifact

    async def test_update_after_delete_with_same_text_restores_document(
        self, env: _Env
    ) -> None:
        """Updating a deleted document with its old text makes it searchable again."""
        key = env.key("doc")
        text = env.text(_BODY)
        schema = _schema(env)
        embedder = _RecordingEmbedder()
        graph = await _open(env, schema, _KeywordExtractor(_full(env)), embedder)
        await graph.add(documents=[_document(key, text)])

        deleted = await graph.delete_document(key)

        # The version has one chunk edge and one section edge.
        assert deleted.parts_closed == 2
        assert await _open_chunks(env.store, key) == []
        assert await _search_chunks(env, embedder, schema, "ada") == []

        restored = await graph.update(key, text=text)

        assert restored.no_op is False
        assert restored.add_result is not None
        assert len(await _open_chunks(env.store, key)) == 1
        assert await _search_chunks(env, embedder, schema, "ada") == [text]
        assert await _entity_names(env.store, env.person) == ["Ada", "Bob"]
        assert await _entity_names(env.store, env.place) == ["Paris"]
        document = await _document_row(env.store, key)
        assert document["content_hash"] == _content_hash(text)
        artifact = {
            "chunks_closed_by_delete": deleted.parts_closed,
            "update_after_delete_no_op": restored.no_op,
            "open_chunks_after_restore": len(await _open_chunks(env.store, key)),
            "entities": await _entity_names(env.store, env.person),
        }
        written = write_artifact("schema_change_after_delete", artifact)
        assert written == artifact

    async def test_failed_update_keeps_committed_version(self, env: _Env) -> None:
        """A failed update keeps the old version, and a retry applies the change."""
        key = env.key("doc")
        first_text = env.text(_BODY)
        second_text = env.text("Bob met Ada. Explode.")
        extractor = _KeywordExtractor(_full(env))
        graph = await _open(env, _schema(env), extractor, _RecordingEmbedder())
        await graph.add(documents=[_document(key, first_text)])
        before = await _document_row(env.store, key)
        before_chunk_ids = _chunk_ids(await _open_chunks(env.store, key))

        extractor.fail_marker = "Explode"
        with pytest.raises(RuntimeError, match="extractor unavailable"):
            await graph.update(key, text=second_text)

        assert await _document_row(env.store, key) == before
        assert _chunk_ids(await _open_chunks(env.store, key)) == before_chunk_ids
        after_failure_people = await _entity_names(env.store, env.person)
        after_failure_places = await _entity_names(env.store, env.place)
        assert after_failure_people == ["Ada", "Bob"]
        assert after_failure_places == ["Paris"]

        extractor.fail_marker = None
        retried = await graph.update(key, text=second_text)

        assert retried.no_op is False
        assert retried.previous_content_hash == _content_hash(first_text)
        assert retried.new_content_hash == _content_hash(second_text)
        document = await _document_row(env.store, key)
        assert document["content_hash"] == _content_hash(second_text)
        assert await _entity_names(env.store, env.place) == []
        artifact = {
            "entities_after_failure": after_failure_people + after_failure_places,
            "retry_no_op": retried.no_op,
            "entities_after_retry": await _entity_names(env.store, env.person),
        }
        written = write_artifact("schema_change_failed_update", artifact)
        assert written == artifact

    async def test_failed_in_place_refresh_keeps_prior_evidence_until_retried(
        self, env: _Env
    ) -> None:
        """A chunk whose refresh fails keeps its evidence and is extracted again."""
        key = env.key("doc")
        text = env.text(_BODY)
        first = await _open(
            env,
            _schema(env, with_relations=True),
            _KeywordExtractor(_full(env), [_knows(env), _mentors(env)]),
            _RecordingEmbedder(),
        )
        await first.add(documents=[_document(key, text)])
        before_rows = await _open_chunks(env.store, key)
        chunk_ids = _chunk_ids(before_rows)
        stamp = before_rows[0]["extraction_fingerprint"]
        knows_before = await _relations(env.store, env.knows)
        mentors_before = await _relations(env.store, env.mentors)

        changed_schema = _schema(
            env, person_description="A human being.", with_relations=True
        )
        failing = _KeywordExtractor(_full(env), [_knows(env), _mentors(env)])
        failing.fail_marker = env.run
        failed_graph = await _open(env, changed_schema, failing, _RecordingEmbedder())
        failed = await failed_graph.update(
            key, text=text, error_policy=ErrorPolicy.SKIP
        )

        assert failed.no_op is False
        assert _chunk_ids(await _open_chunks(env.store, key)) == chunk_ids
        after_failure = await _mentioned_names(env.store, chunk_ids)
        assert after_failure == ["Ada", "Bob", "Paris"]
        assert await _relations(env.store, env.knows) == knows_before
        assert await _relations(env.store, env.mentors) == mentors_before
        failed_stamps = await _open_chunks(env.store, key)
        assert {row["extraction_fingerprint"] for row in failed_stamps} == {stamp}

        healthy = _KeywordExtractor(_people(env), [_knows(env)])
        retry_graph = await _open(env, changed_schema, healthy, _RecordingEmbedder())
        retried = await retry_graph.update(
            key, text=text, error_policy=ErrorPolicy.SKIP
        )

        assert retried.no_op is False
        retried_rows = await _open_chunks(env.store, key)
        retried_stamps = {row["extraction_fingerprint"] for row in retried_rows}
        assert len(retried_stamps) == 1
        assert retried_stamps != {stamp}
        assert await _mentioned_names(env.store, chunk_ids) == ["Ada", "Bob"]
        assert await _entity_names(env.store, env.place) == []
        assert await _relations(env.store, env.mentors) == []

        again = await retry_graph.update(key, text=text, error_policy=ErrorPolicy.SKIP)

        assert again.no_op is True
        artifact = {
            "failed_no_op": failed.no_op,
            "entities_after_failure": after_failure,
            "retried_no_op": retried.no_op,
            "entities_after_retry": await _mentioned_names(env.store, chunk_ids),
            "repeat_no_op": again.no_op,
        }
        written = write_artifact("schema_change_failed_refresh", artifact)
        assert written == artifact

    async def test_failed_new_version_is_extracted_again_on_next_update(
        self, env: _Env
    ) -> None:
        """A new version whose extraction failed is not treated as current."""
        key = env.key("doc")
        first_text = env.text(_BODY)
        second_text = env.text("Bob met Ada.")
        graph = await _open(
            env, _schema(env), _KeywordExtractor(_full(env)), _RecordingEmbedder()
        )
        await graph.add(documents=[_document(key, first_text)])

        failing = _KeywordExtractor(_full(env))
        failing.fail_marker = env.run
        failing_graph = await _open(env, _schema(env), failing, _RecordingEmbedder())
        failed = await failing_graph.update(
            key, text=second_text, error_policy=ErrorPolicy.SKIP
        )

        assert failed.no_op is False
        failed_rows = await _open_chunks(env.store, key)
        assert {row["extraction_fingerprint"] for row in failed_rows} == {None}

        retried = await graph.update(key, text=second_text)

        assert retried.no_op is False
        retried_ids = _chunk_ids(await _open_chunks(env.store, key))
        assert await _mentioned_names(env.store, retried_ids) == ["Ada", "Bob"]

        again = await graph.update(key, text=second_text)

        assert again.no_op is True
        artifact = {
            "failed_no_op": failed.no_op,
            "retried_no_op": retried.no_op,
            "entities_after_retry": await _mentioned_names(env.store, retried_ids),
            "repeat_no_op": again.no_op,
        }
        written = write_artifact("schema_change_failed_new_version", artifact)
        assert written == artifact

    async def test_failed_first_add_is_extracted_again_on_next_update(
        self, env: _Env
    ) -> None:
        """A first add whose extraction failed is not treated as current."""
        key = env.key("doc")
        text = env.text(_BODY)
        failing = _KeywordExtractor(_full(env))
        failing.fail_marker = env.run
        failing_graph = await _open(env, _schema(env), failing, _RecordingEmbedder())
        added = await failing_graph.add(
            documents=[_document(key, text)], error_policy=ErrorPolicy.SKIP
        )

        assert len(added.extraction.failures) == 1
        added_rows = await _open_chunks(env.store, key)
        assert {row["extraction_fingerprint"] for row in added_rows} == {None}

        graph = await _open(
            env, _schema(env), _KeywordExtractor(_full(env)), _RecordingEmbedder()
        )
        retried = await graph.update(key, text=text)

        assert retried.no_op is False
        retried_ids = _chunk_ids(await _open_chunks(env.store, key))
        assert await _mentioned_names(env.store, retried_ids) == [
            "Ada",
            "Bob",
            "Paris",
        ]

        again = await graph.update(key, text=text)

        assert again.no_op is True
        artifact = {
            "added_failures": len(added.extraction.failures),
            "retried_no_op": retried.no_op,
            "entities_after_retry": await _mentioned_names(env.store, retried_ids),
            "repeat_no_op": again.no_op,
        }
        written = write_artifact("schema_change_failed_first_add", artifact)
        assert written == artifact
