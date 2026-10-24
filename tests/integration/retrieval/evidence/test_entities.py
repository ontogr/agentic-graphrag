"""Integration tests for entity search and bounded entity exploration.

The fixture adds three short documents through the public Graph API with a
keyword extractor, so entities, mentions and typed relations come from the real
ingestion path. The embedder maps each keyword to one axis of a four-dimensional
vector. Every entity label, relation type and document key carries a per-run id,
so tests can share one database.
"""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from uuid import uuid4

import pytest

from agrag.chunking import Chunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity_search import (
    EdgeKind,
    EntityKind,
    EntityResult,
    ExplorationBound,
    ExplorationStatus,
)
from agrag.common.data_models.evidence import (
    EvidenceSearchMode,
    EvidenceSearchStatus,
    FetchStatus,
)
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.embedding.base import Embedder
from agrag.evidence import entity_search, explore_relationships, fetch_evidence
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.common import text_sections
from tests.integration._backend import await_indexes, build_test_store
from tests.integration.retrieval.evidence._corpus import sha256_of


_KEYWORD_AXES: dict[str, tuple[float, float, float, float]] = {
    "aspirin": (1.0, 0.0, 0.0, 0.0),
    "ibuprofen": (0.0, 1.0, 0.0, 0.0),
    "headache": (0.0, 0.0, 1.0, 0.0),
    "fever": (0.0, 0.0, 0.0, 1.0),
}
_KEYWORD_TEXT = {
    "aspirin": "Aspirin",
    "ibuprofen": "Ibuprofen",
    "headache": "Headache",
    "fever": "Fever",
}
_KEYWORD_LABEL = {"aspirin": "drug", "ibuprofen": "drug"}


class _KeywordEmbedder(Embedder):
    """Embedder whose vectors follow the keywords in the text."""

    model = "keyword"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Sum the axis of each keyword found, plus a small constant."""
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vector = [0.01] * 4
            for keyword, axis in _KEYWORD_AXES.items():
                if keyword in lowered:
                    vector = [v + a for v, a in zip(vector, axis, strict=True)]
            vectors.append(vector)
        return vectors


class _KeywordExtractor(Extractor):
    """Extractor that finds the keywords, and a treats relation between them.

    A drug keyword and a condition keyword in one chunk give one relation. The
    relation label comes from the run's schema, so tests can add their own types.
    """

    def __init__(self, labels: dict[str, str], treats_label: str) -> None:
        """Map each keyword to its entity label and name the relation label."""
        self._labels = labels
        self._treats = treats_label

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return one mention per keyword and a treats relation when it applies."""
        lowered = chunk.text.lower()
        mentions: list[ExtractedEntity] = []
        positions: dict[str, int] = {}
        for keyword in _KEYWORD_AXES:
            start = lowered.find(keyword)
            if start < 0:
                continue
            positions[keyword] = len(mentions)
            mentions.append(
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._labels[keyword],
                    text=_KEYWORD_TEXT[keyword],
                    char_start=start,
                    char_end=start + len(keyword),
                )
            )
        relations: list[ExtractedRelation] = []
        if "aspirin" in positions and "headache" in positions:
            relations.append(
                _relation(chunk, self._treats, positions, "aspirin", "headache")
            )
        if "aspirin" in positions and "fever" in positions:
            relations.append(
                _relation(chunk, self._treats, positions, "aspirin", "fever")
            )
        if "ibuprofen" in positions and "fever" in positions:
            relations.append(
                _relation(chunk, self._treats, positions, "ibuprofen", "fever")
            )
        return ExtractionResult(
            entities=mentions, relations=relations, extractor_name="keyword"
        )


def _relation(
    chunk: Chunk,
    label: str,
    positions: dict[str, int],
    source: str,
    target: str,
) -> ExtractedRelation:
    """Build a relation between two keyword mentions of one chunk."""
    return ExtractedRelation(
        chunk_id=chunk.id,
        label=label,
        source_index=positions[source],
        target_index=positions[target],
    )


def _document(key: str, text: str) -> Document:
    """Build a prose document with an explicit key and one section."""
    return Document(
        text=text,
        title=key.rsplit("/", 1)[-1],
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=sha256_of(text),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=1,
        sections=text_sections(text),
    )


@dataclass
class EntityEnv:
    """A graph loaded with the keyword documents, under one run id.

    Attributes:
        run: The per-test id that labels and document keys carry.
        store: The connected graph store.
        graph: The graph that wrote the documents.
        drug: The drug entity label of this run.
        condition: The condition entity label of this run.
        treats: The treats relation type of this run.
        links: A relation type with no evidence, written directly in tests.
    """

    run: str
    store: GraphStore
    graph: Graph
    drug: str
    condition: str
    treats: str
    links: str

    def key(self, name: str) -> str:
        """Return the document key for a short name."""
        return f"entities://{self.run}/{name}"

    @property
    def headache_note(self) -> str:
        """Return the key of the note that mentions aspirin and headache."""
        return self.key("headache")

    @property
    def fever_note(self) -> str:
        """Return the key of the note that mentions ibuprofen and fever."""
        return self.key("fever")

    @property
    def aspirin_fever_note(self) -> str:
        """Return the key of the note that mentions aspirin and fever."""
        return self.key("aspirin_fever")


async def _cleanup(env: EntityEnv) -> None:
    """Delete the nodes this run wrote, leaving the shared database as it was."""
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
        "MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c",
        {"prefix": env.key("")},
    )
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix DETACH DELETE d",
        {"prefix": env.key("")},
    )
    await env.store.execute_write(
        "MATCH (n) WHERE any(label IN labels(n) WHERE label ENDS WITH $run) "
        "DETACH DELETE n",
        {"run": env.run},
    )


@pytest.fixture
async def entity_env() -> AsyncGenerator[EntityEnv, None]:
    """Open a graph with the run's schema and add the keyword documents."""
    run = uuid4().hex[:8]
    drug = f"Drug{run}"
    condition = f"Condition{run}"
    treats = f"TREATS{run}"
    links = f"LINKS{run}"
    schema = GraphSchema(
        name="entities",
        version="1",
        entities=[
            EntityType(label=drug, description="A medicine."),
            EntityType(label=condition, description="A health problem."),
        ],
        relations=[
            RelationType(
                label=treats,
                description="A medicine treats a condition.",
                patterns=[(drug, condition)],
            ),
            RelationType(
                label=links,
                description="A link written without evidence.",
                patterns=[(drug, drug)],
            ),
        ],
    )
    store = build_test_store()
    labels = {
        "aspirin": drug,
        "ibuprofen": drug,
        "headache": condition,
        "fever": condition,
    }
    graph = await Graph.open(
        schema=schema,
        graph_store=store,
        embedder=_KeywordEmbedder(),
        extractor=_KeywordExtractor(labels, treats),
        chunker=Chunker(size=200),
    )
    env = EntityEnv(
        run=run,
        store=store,
        graph=graph,
        drug=drug,
        condition=condition,
        treats=treats,
        links=links,
    )
    try:
        await await_indexes(store)
        await graph.add(
            documents=[
                _document(env.headache_note, "Aspirin relieves headache in adults."),
                _document(env.fever_note, "Ibuprofen reduces fever after surgery."),
                _document(env.aspirin_fever_note, "Aspirin also helps with fever."),
            ]
        )
        yield env
    finally:
        try:
            await _cleanup(env)
        finally:
            await store.close()


async def _entity_id(env: EntityEnv, name: str, scope: frozenset[str]) -> str:
    """Return the id of the entity with a name, found through the graph."""
    result = await entity_search(
        env.store,
        _KeywordEmbedder(),
        name,
        scope=scope,
        labels=[env.drug, env.condition],
        limit=5,
        mode=EvidenceSearchMode.LEXICAL,
    )
    [hit] = [hit for hit in result.hits if hit.name == name]
    return hit.entity_id


def _names(result: EntityResult) -> list[str]:
    """Return the names of the hits, best first."""
    return [hit.name for hit in result.hits]


class TestFindEntities:
    """Entity search returns entities with their visible supporting passages."""

    async def test_index_listing_names_the_labels_with_a_vector_index(
        self, entity_env: EntityEnv
    ) -> None:
        """The index listing behind the default label set has the entity labels."""
        indexes = await entity_env.store.list_indexes()

        labels = {
            label
            for index in indexes
            if index.type == "VECTOR" and index.properties == ["embedding"]
            for label in index.labels
        }
        assert {entity_env.drug, entity_env.condition} <= labels

    async def test_every_hit_is_supported_by_fetchable_text_with_the_mention(
        self, entity_env: EntityEnv
    ) -> None:
        """Each supported hit cites a passage whose text holds the entity name."""
        scope = frozenset({entity_env.headache_note, entity_env.fever_note})

        result = await entity_search(
            entity_env.store,
            _KeywordEmbedder(),
            "aspirin headache ibuprofen fever",
            scope=scope,
            labels=[entity_env.drug, entity_env.condition],
            limit=10,
            mode=EvidenceSearchMode.LEXICAL,
        )

        assert result.status is EvidenceSearchStatus.OK
        assert _names(result)
        for hit in result.hits:
            assert hit.kind is EntityKind.SUPPORTED
            assert hit.support
            fetched = await fetch_evidence(
                entity_env.store,
                [support.evidence_id for support in hit.support],
                scope=scope,
                max_chars=10_000,
            )
            for outcome in fetched.outcomes:
                assert outcome.status is FetchStatus.OK
                assert hit.name.lower() in (outcome.text or "").lower()

    @pytest.mark.parametrize(
        "mode",
        [
            EvidenceSearchMode.LEXICAL,
            EvidenceSearchMode.SEMANTIC,
            EvidenceSearchMode.HYBRID,
        ],
    )
    async def test_each_mode_finds_the_entity_by_its_name(
        self, entity_env: EntityEnv, mode: EvidenceSearchMode
    ) -> None:
        """Lexical, semantic and hybrid search all return the named entity."""
        result = await entity_search(
            entity_env.store,
            _KeywordEmbedder(),
            "aspirin",
            scope=frozenset({entity_env.headache_note}),
            labels=[entity_env.drug],
            limit=5,
            mode=mode,
        )

        assert result.status is EvidenceSearchStatus.OK
        assert _names(result)[0] == "Aspirin"

    async def test_operator_characters_in_the_query_are_plain_terms(
        self, entity_env: EntityEnv
    ) -> None:
        """Lucene operators in the query do not break the lexical search."""
        result = await entity_search(
            entity_env.store,
            _KeywordEmbedder(),
            'aspirin" OR (*) AND NOT :~ fever^',
            scope=frozenset({entity_env.headache_note, entity_env.aspirin_fever_note}),
            labels=[entity_env.drug],
            limit=5,
            mode=EvidenceSearchMode.LEXICAL,
        )

        assert result.status is EvidenceSearchStatus.OK
        assert "Aspirin" in _names(result)

    async def test_scope_removes_an_entity_supported_only_out_of_scope(
        self, entity_env: EntityEnv
    ) -> None:
        """An entity whose only passages are out of scope is not returned."""
        out_of_scope = await entity_search(
            entity_env.store,
            _KeywordEmbedder(),
            "ibuprofen",
            scope=frozenset({entity_env.headache_note}),
            labels=[entity_env.drug],
            limit=5,
            mode=EvidenceSearchMode.LEXICAL,
        )
        in_scope = await entity_search(
            entity_env.store,
            _KeywordEmbedder(),
            "ibuprofen",
            scope=frozenset({entity_env.fever_note}),
            labels=[entity_env.drug],
            limit=5,
            mode=EvidenceSearchMode.LEXICAL,
        )

        assert "Ibuprofen" not in _names(out_of_scope)
        assert "Ibuprofen" in _names(in_scope)

    async def test_entity_whose_only_passage_is_superseded_is_never_supported(
        self, entity_env: EntityEnv
    ) -> None:
        """A superseded-only entity is never returned with a supporting passage.

        Ingestion deletes an entity that loses all its evidence on update, so the
        entity is normally absent. If a hit is returned, it must be unsupported and
        carry no passage.
        """
        await entity_env.graph.update(
            entity_env.fever_note, text="Fever needs rest and fluids."
        )

        result = await entity_search(
            entity_env.store,
            _KeywordEmbedder(),
            "ibuprofen",
            scope=frozenset({entity_env.fever_note}),
            labels=[entity_env.drug],
            limit=5,
            mode=EvidenceSearchMode.LEXICAL,
        )

        for hit in result.hits:
            if hit.name == "Ibuprofen":
                assert hit.kind is EntityKind.UNSUPPORTED
                assert hit.support == []

    async def test_support_is_limited_to_support_limit(
        self, entity_env: EntityEnv
    ) -> None:
        """No hit lists more supporting passages than support_limit allows."""
        result = await entity_search(
            entity_env.store,
            _KeywordEmbedder(),
            "fever",
            scope=frozenset({entity_env.fever_note, entity_env.aspirin_fever_note}),
            labels=[entity_env.condition],
            limit=5,
            mode=EvidenceSearchMode.LEXICAL,
            support_limit=1,
        )

        [fever] = [hit for hit in result.hits if hit.name == "Fever"]
        assert len(fever.support) == 1


class TestExplore:
    """Exploration follows typed relations with bounds and support kinds."""

    async def test_supported_relation_is_an_assertion_with_fetchable_evidence(
        self, entity_env: EntityEnv
    ) -> None:
        """A relation with chunk support is an assertion, and its support fetches."""
        scope = frozenset({entity_env.headache_note})
        aspirin = await _entity_id(entity_env, "Aspirin", scope)

        result = await explore_relationships(
            entity_env.store,
            aspirin,
            scope=scope,
            relation_types=[entity_env.treats],
        )

        assert result.status is ExplorationStatus.OK
        [edge] = result.edges
        assert edge.relation_type == entity_env.treats
        assert edge.kind is EdgeKind.ASSERTION
        assert edge.evidence
        fetched = await fetch_evidence(
            entity_env.store,
            [passage.evidence_id for passage in edge.evidence],
            scope=scope,
            max_chars=10_000,
        )
        assert all(
            "headache" in (outcome.text or "").lower() for outcome in fetched.outcomes
        )

    async def test_relation_without_evidence_is_a_path(
        self, entity_env: EntityEnv
    ) -> None:
        """A connection with no supporting passage is labelled a path."""
        scope = frozenset({entity_env.headache_note, entity_env.fever_note})
        aspirin = await _entity_id(entity_env, "Aspirin", scope)
        ibuprofen = await _entity_id(entity_env, "Ibuprofen", scope)
        await entity_env.store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type=entity_env.links,
                    start_id=aspirin,
                    end_id=ibuprofen,
                    properties={"source_chunk_ids": []},
                )
            ]
        )

        result = await explore_relationships(
            entity_env.store,
            aspirin,
            scope=scope,
            relation_types=[entity_env.links],
        )

        [edge] = result.edges
        assert edge.kind is EdgeKind.PATH
        assert edge.evidence == []

    async def test_depth_one_reports_the_depth_bound_when_more_lies_beyond(
        self, entity_env: EntityEnv
    ) -> None:
        """Depth one stops at the neighbors and reports that more lies beyond."""
        scope = frozenset(
            {
                entity_env.headache_note,
                entity_env.fever_note,
                entity_env.aspirin_fever_note,
            }
        )
        aspirin = await _entity_id(entity_env, "Aspirin", scope)

        result = await explore_relationships(
            entity_env.store, aspirin, scope=scope, depth=1, max_nodes=25
        )

        assert ExplorationBound.DEPTH in result.truncated_by
        assert all(node.depth == 1 for node in result.nodes)
        assert {node.name for node in result.nodes} == {"Headache", "Fever"}

    async def test_depth_two_reaches_the_second_hop(
        self, entity_env: EntityEnv
    ) -> None:
        """Depth two reaches the entity behind the neighbor."""
        scope = frozenset(
            {
                entity_env.headache_note,
                entity_env.fever_note,
                entity_env.aspirin_fever_note,
            }
        )
        aspirin = await _entity_id(entity_env, "Aspirin", scope)

        result = await explore_relationships(
            entity_env.store, aspirin, scope=scope, depth=2, max_nodes=25
        )

        assert "Ibuprofen" in {node.name for node in result.nodes}
        assert ExplorationBound.DEPTH not in result.truncated_by

    async def test_node_bound_truncates_a_hub(self, entity_env: EntityEnv) -> None:
        """A hub with more neighbors than max_nodes reports the node bound."""
        scope = frozenset({entity_env.headache_note, entity_env.aspirin_fever_note})
        aspirin = await _entity_id(entity_env, "Aspirin", scope)

        result = await explore_relationships(
            entity_env.store, aspirin, scope=scope, depth=1, max_nodes=1
        )

        assert len(result.nodes) == 1
        assert result.truncated is True
        assert ExplorationBound.NODES in result.truncated_by

    async def test_edge_bound_truncates_the_result(self, entity_env: EntityEnv) -> None:
        """More edges than max_edges report the edge bound and stop there."""
        scope = frozenset({entity_env.headache_note, entity_env.aspirin_fever_note})
        aspirin = await _entity_id(entity_env, "Aspirin", scope)

        result = await explore_relationships(
            entity_env.store, aspirin, scope=scope, depth=1, max_edges=1
        )

        assert len(result.edges) == 1
        assert ExplorationBound.EDGES in result.truncated_by

    async def test_relation_types_filter_excludes_other_types(
        self, entity_env: EntityEnv
    ) -> None:
        """A relation type that does not match returns no edges."""
        scope = frozenset({entity_env.headache_note})
        aspirin = await _entity_id(entity_env, "Aspirin", scope)

        result = await explore_relationships(
            entity_env.store,
            aspirin,
            scope=scope,
            relation_types=[entity_env.links],
        )

        assert result.status is ExplorationStatus.OK
        assert result.edges == []

    async def test_start_entity_without_visible_support_is_unavailable(
        self, entity_env: EntityEnv
    ) -> None:
        """A start entity with no passage in scope gives unavailable."""
        aspirin = await _entity_id(
            entity_env,
            "Aspirin",
            frozenset({entity_env.headache_note}),
        )

        result = await explore_relationships(
            entity_env.store,
            aspirin,
            scope=frozenset({entity_env.fever_note}),
        )

        assert result.status is ExplorationStatus.UNAVAILABLE
        assert result.nodes == []

    @pytest.mark.parametrize("depth", [0, 3])
    async def test_rejects_a_depth_outside_one_to_two(
        self, entity_env: EntityEnv, depth: int
    ) -> None:
        """A depth below one or above two raises ValueError."""
        with pytest.raises(ValueError):
            await explore_relationships(
                entity_env.store,
                str(uuid4()),
                scope=frozenset({entity_env.headache_note}),
                depth=depth,
            )
