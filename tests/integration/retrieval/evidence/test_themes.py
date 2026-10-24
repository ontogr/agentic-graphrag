"""Integration tests for search_themes over an ingested corpus with entities.

The corpus is two small documents whose named people are extracted by a fake
extractor, so community detection runs without an LLM or a network. The
community reports are mocked, and every theme query is checked against the
passages the tool returns, never against report text.
"""

import importlib.util
from collections.abc import AsyncGenerator, Sequence
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.chunking import Chunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.evidence import (
    EvidenceSearchStatus,
)
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.common.data_models.theme_search import ThemeHit, ThemeResult
from agrag.cypher.entities import validate_identifier
from agrag.cypher.schema import vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence import fetch_evidence, search_themes
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.integration._backend import await_indexes, build_test_store
from tests.integration.retrieval.evidence._corpus import (
    make_document,
)


graspologic_missing = importlib.util.find_spec("graspologic_native") is None

_TEAM_TEXT = (
    "Team Notes. Alice and Bob work at Acme and keep the activity records of "
    "the office."
)
_OFFSITE_TEXT = (
    "Offsite Notes. Alice and Bob joined the Acme offsite at the harbor "
    "lighthouse. Carol and Dave from Globex came too."
)
_OFFSITE_UPDATE = "Offsite Notes. The spring offsite moved to the pier boathouse."
_PEOPLE = ["alice", "bob", "carol", "dave"]
_ORGS = ["acme", "globex"]


class _TeamEmbedder(Embedder):
    """Bag-of-words-style embedder on four axes for the team corpus."""

    model = "team-bag-of-words"

    async def dimensions(self) -> int:
        """Return the number of axes."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one count vector per text over the known names and words."""
        words = {"alice": 0, "bob": 0, "carol": 1, "dave": 1, "acme": 2, "globex": 3}
        vectors = []
        for text in texts:
            vector = [0.01] * 4
            for word, axis in words.items():
                if word in text.lower():
                    vector[axis] += 1.0
            vectors.append(vector)
        return vectors


class _TeamExtractor(Extractor):
    """Extractor that finds the named people, their orgs, and WORKS_AT edges."""

    def __init__(self, person_label: str, org_label: str) -> None:
        self._person_label = person_label
        self._org_label = org_label

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract known people and orgs found in the chunk text."""
        text_lower = chunk.text.lower()
        entities: list[ExtractedEntity] = []
        person_seen: dict[str, int] = {}
        org_seen: dict[str, int] = {}
        for name in _PEOPLE:
            index = text_lower.find(name)
            if index >= 0:
                person_seen[name] = len(entities)
                entities.append(
                    ExtractedEntity(
                        chunk_id=chunk.id,
                        label=self._person_label,
                        text=name.capitalize(),
                        char_start=index,
                        char_end=index + len(name),
                    )
                )
        for org in _ORGS:
            index = text_lower.find(org)
            if index >= 0:
                org_seen[org] = len(entities)
                entities.append(
                    ExtractedEntity(
                        chunk_id=chunk.id,
                        label=self._org_label,
                        text=org.capitalize(),
                        char_start=index,
                        char_end=index + len(org),
                    )
                )
        relations = [
            ExtractedRelation(
                chunk_id=chunk.id,
                label="WORKS_AT",
                source_index=person_seen[person],
                target_index=org_seen[org],
            )
            for person, org in (("alice", "acme"), ("carol", "globex"))
            if person in person_seen and org in org_seen
        ]
        return ExtractionResult(
            entities=entities, relations=relations, extractor_name="fake"
        )


def _fake_reports(communities: Sequence[object], **_: object) -> list[MagicMock]:
    """Return one fake LLM report per requested community."""
    return [
        MagicMock(
            title="LLM Title",
            summary="LLM summary.",
            rating=7.0,
            rating_explanation="ok",
            findings=["f1"],
        )
        for _ in communities
    ]


class ThemesEnv:
    """A graph with the team corpus, before or after community detection.

    Attributes:
        store: The connected graph store.
        graph: The graph that wrote the corpus.
        team_key: The key of the team document.
        offsite_key: The key of the offsite document.
    """

    def __init__(self, store, graph: Graph, team_key: str, offsite_key: str) -> None:
        """Hold the store, the graph, and the two document keys."""
        self.store = store
        self.graph = graph
        self.team_key = team_key
        self.offsite_key = offsite_key

    @property
    def scope(self) -> frozenset[str]:
        """Return the scope of both documents."""
        return frozenset({self.team_key, self.offsite_key})


async def _cleanup(store, team_key: str, offsite_key: str) -> None:
    """Delete the corpus documents and every community of the run."""
    for key in (team_key, offsite_key):
        await store.execute_write(
            "MATCH (d:Document) WHERE d.document_key = $key "
            "MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c",
            {"key": key},
        )
        await store.execute_write(
            "MATCH (d:Document) WHERE d.document_key = $key DETACH DELETE d",
            {"key": key},
        )
    await store.execute_write(f"MATCH (c:{COMMUNITY_LABEL}) DETACH DELETE c", {})


@pytest.fixture
async def themes_env() -> AsyncGenerator[ThemesEnv, None]:
    """Open a graph with the team corpus and no communities yet."""
    run = uuid4().hex[:8]
    person_label = validate_identifier(f"Person_{run}")
    org_label = validate_identifier(f"Org_{run}")
    team_key = f"evidence://{run}/team"
    offsite_key = f"evidence://{run}/offsite"
    schema = GraphSchema(
        name="themes",
        version="1",
        entities=[
            EntityType(label=person_label, description="A person."),
            EntityType(label=org_label, description="An organization."),
        ],
        relations=[
            RelationType(
                label="WORKS_AT",
                description="A person works at an organization.",
                patterns=[(person_label, org_label)],
            )
        ],
    )
    store = build_test_store()
    graph = await Graph.open(
        schema=schema,
        graph_store=store,
        embedder=_TeamEmbedder(),
        extractor=_TeamExtractor(person_label, org_label),
        chunker=Chunker(size=60),
    )
    await await_indexes(store)
    await graph.add(
        documents=[
            make_document(team_key, _TEAM_TEXT),
            make_document(offsite_key, _OFFSITE_TEXT),
        ]
    )
    env = ThemesEnv(store, graph, team_key, offsite_key)
    try:
        yield env
    finally:
        await _cleanup(store, team_key, offsite_key)


async def _detect(env: ThemesEnv) -> None:
    """Run community detection with mocked LLM reports."""
    with patch(
        "agrag.llm.baml_client.b.SummarizeCommunities",
        new_callable=AsyncMock,
        side_effect=_fake_reports,
    ):
        await env.graph.detect_communities(apply=True)


class TestThemeIndexReadiness:
    """Theme search reports whether its Community index can be read."""

    async def test_hidden_community_index_reports_not_ready(
        self,
        themes_env: ThemesEnv,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A Community vector index that is not ONLINE gives index_not_ready."""
        store = themes_env.store
        name = vector_index_name(COMMUNITY_LABEL, "embedding")
        original = store.list_indexes

        async def list_indexes(*, timeout=None):
            indexes = await original(timeout=timeout)
            return [index for index in indexes if index.name != name]

        monkeypatch.setattr(store, "list_indexes", list_indexes)

        result = await search_themes(
            store,
            _TeamEmbedder(),
            "acme team",
            scope=themes_env.scope,
        )

        assert result.status is EvidenceSearchStatus.INDEX_NOT_READY
        assert result.themes == []


@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
class TestSearchThemes:
    """search_themes returns scoped, fetchable passages for detected themes."""

    async def test_no_match_before_the_first_detection_run(
        self, themes_env: ThemesEnv
    ) -> None:
        """The Community index exists but is empty, so the result is no_match."""
        result = await search_themes(
            themes_env.store,
            _TeamEmbedder(),
            "acme team",
            scope=themes_env.scope,
        )

        assert result.status is EvidenceSearchStatus.NO_MATCH
        assert result.themes == []
        assert result.index_state is not None

    async def test_returns_scoped_passages_that_fetch_resolves(
        self, themes_env: ThemesEnv
    ) -> None:
        """After detection, each theme's passages fetch as complete text."""
        await _detect(themes_env)

        result = await search_themes(
            themes_env.store,
            _TeamEmbedder(),
            "acme team",
            scope=themes_env.scope,
        )

        assert result.status is EvidenceSearchStatus.OK
        assert result.themes
        for theme in result.themes:
            assert set(theme.model_dump()) == {
                "theme_id",
                "score",
                "entities",
                "passages",
            }
            assert theme.passages
            assert len(theme.entities) <= 5
        first_passage = result.themes[0].passages[0]
        fetched = await fetch_evidence(
            themes_env.store,
            [first_passage.evidence_id],
            scope=themes_env.scope,
        )
        assert fetched.outcomes[0].status.value == "ok"
        assert fetched.outcomes[0].text

    async def test_narrow_scope_returns_only_that_document(
        self, themes_env: ThemesEnv
    ) -> None:
        """A scope of one document returns only passages of that document."""
        await _detect(themes_env)

        result = await search_themes(
            themes_env.store,
            _TeamEmbedder(),
            "acme team",
            scope=frozenset({themes_env.team_key}),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert result.themes
        document_keys = {
            passage.document_key
            for theme in result.themes
            for passage in theme.passages
        }
        assert document_keys == {themes_env.team_key}

    async def test_deleted_document_disappears_without_rerunning_detection(
        self, themes_env: ThemesEnv
    ) -> None:
        """A soft-deleted document contributes no passage after deletion."""
        await _detect(themes_env)
        await themes_env.graph.delete_document(themes_env.offsite_key)

        result = await search_themes(
            themes_env.store,
            _TeamEmbedder(),
            "acme team",
            scope=themes_env.scope,
        )

        document_keys = {
            passage.document_key
            for theme in result.themes
            for passage in theme.passages
        }
        assert themes_env.offsite_key not in document_keys

    async def test_superseded_text_disappears_without_rerunning_detection(
        self, themes_env: ThemesEnv
    ) -> None:
        """An updated document contributes only passages of its new version."""
        await _detect(themes_env)
        await themes_env.graph.update(themes_env.team_key, text=_OFFSITE_UPDATE)

        result = await search_themes(
            themes_env.store,
            _TeamEmbedder(),
            "acme team",
            scope=themes_env.scope,
        )

        passages = [passage for theme in result.themes for passage in theme.passages]
        assert all(passage.document_key != themes_env.team_key for passage in passages)


@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
class TestThemeFreshness:
    """Theme results carry the stale-version marker of their corpus."""

    async def test_theme_ids_stay_stable_across_calls(
        self, themes_env: ThemesEnv
    ) -> None:
        """Two searches with the same query return the same theme ids."""
        await _detect(themes_env)

        first: ThemeResult = await search_themes(
            themes_env.store,
            _TeamEmbedder(),
            "acme team",
            scope=themes_env.scope,
        )
        second: ThemeResult = await search_themes(
            themes_env.store,
            _TeamEmbedder(),
            "acme team",
            scope=themes_env.scope,
        )

        assert [theme.theme_id for theme in first.themes] == [
            theme.theme_id for theme in second.themes
        ]
        assert first.failures == []
        assert all(isinstance(theme, ThemeHit) for theme in first.themes)
