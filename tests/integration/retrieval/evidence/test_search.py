"""Integration tests for evidence search over the authored corpus.

Search runs against a real Neo4j with the authored corpus from ``_corpus``.
The embedder is the bag-of-words fake, so the semantic leg is deterministic.
Gold passages are found by locating authored sentences, and a hit covers a
gold passage when its chunk range contains the gold range.
"""

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.evidence import (
    EvidenceSearchHit,
    EvidenceSearchLeg,
    EvidenceSearchMode,
    EvidenceSearchResult,
    EvidenceSearchStatus,
    FetchStatus,
    IndexState,
    LegFailure,
)
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.evidence import fetch_evidence, search_evidence
from agrag.graphdb.neo4j import Neo4jGraphStore
from tests.integration.retrieval.evidence._corpus import (
    GOLD_SENTENCE,
    HARBOR_TEXT_V2,
    HEADED_HEADING,
    KEEP_TEXT,
    BagOfWordsEmbedder,
    locate,
    make_document,
    make_headed_document,
    sha256_of,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


_QUERY = "do you keep and upload my activity to your database"
_GOLD_START, _GOLD_END = locate(KEEP_TEXT, GOLD_SENTENCE)


def _covers_gold(hit: EvidenceSearchHit) -> bool:
    """Return whether a hit's chunk range contains the gold sentence."""
    location = hit.location
    if location.char_start is None or location.char_end is None:
        return False
    return location.char_start <= _GOLD_START and location.char_end >= _GOLD_END


def _gold_positions(hits: list[EvidenceSearchHit]) -> list[int]:
    """Return the 0-based positions of hits that cover the gold sentence."""
    return [index for index, hit in enumerate(hits) if _covers_gold(hit)]


def _hide_index(
    store: Neo4jGraphStore, monkeypatch: pytest.MonkeyPatch, *, name: str, state: str
) -> None:
    """Make SHOW INDEXES report one index in a given state, or leave it out.

    A test database shares one set of indexes across parallel workers, so the
    readiness check is exercised by changing what the store reports for one
    index. The real index is never dropped.
    """
    original = store.execute_read

    async def execute_read(
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        rows = await original(query, parameters, timeout=timeout)
        if "SHOW INDEXES" not in query:
            return rows
        if state == "missing":
            return [row for row in rows if row["name"] != name]
        return [{**row, "state": state} if row["name"] == name else row for row in rows]

    monkeypatch.setattr(store, "execute_read", execute_read)


@pytest.fixture
def embedder() -> Iterator[BagOfWordsEmbedder]:
    """Return a fresh bag-of-words embedder."""
    yield BagOfWordsEmbedder()


class TestLexicalSearch:
    """Full-text search finds the gold passage among the authored documents."""

    async def test_finds_the_gold_passage_within_the_top_five(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """The gold chunk ranks in the top five lexical hits from the Keep notice."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset(
                {evidence_env.keep, evidence_env.viber, evidence_env.harbor}
            ),
        )

        assert result.status is EvidenceSearchStatus.OK
        positions = _gold_positions(result.hits)
        assert positions and positions[0] < 5
        assert result.hits[positions[0]].document_key == evidence_env.keep
        assert result.hits[positions[0]].legs == [EvidenceSearchLeg.LEXICAL]

    async def test_query_with_lucene_operators_is_safe(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """Operator characters and keywords in user text are treated as plain terms."""
        hostile = 'keep AND (upload OR) NOT ~2 "database" +activity -my : ^ \\ [ ] {x}'

        result = await search_evidence(
            evidence_env.store,
            embedder,
            hostile,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert _gold_positions(result.hits)

    async def test_no_match_gives_an_empty_list_with_a_clear_status(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """A query with no indexed term returns no hits and the no-match status."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            "xylophone quasar zeppelin",
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep, evidence_env.viber}),
        )

        assert result.hits == []
        assert result.status is EvidenceSearchStatus.NO_MATCH
        assert result.failures == []
        assert result.index_state is IndexState.READY

    async def test_query_without_any_term_is_no_match(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """A query made only of symbols has no terms, so it matches nothing."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            "+++ ((( ]]]",
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )

        assert result.hits == []
        assert result.status is EvidenceSearchStatus.NO_MATCH
        assert result.failures == []


class TestSemanticSearch:
    """Vector search finds the gold passage with the bag-of-words embedder."""

    async def test_finds_the_gold_passage_within_the_top_five(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """The gold chunk ranks in the top five semantic hits."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.SEMANTIC,
            limit=5,
            scope=frozenset(
                {evidence_env.keep, evidence_env.viber, evidence_env.harbor}
            ),
        )

        assert result.status is EvidenceSearchStatus.OK
        positions = _gold_positions(result.hits)
        assert positions and positions[0] < 5
        assert result.hits[positions[0]].legs == [EvidenceSearchLeg.SEMANTIC]


class TestHeadedChunks:
    """A chunk whose text starts with a heading is addressed by a chunk id."""

    async def test_headed_chunk_hit_fetches_the_chunk_text(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """A hit on a headed chunk has a chunk id, and fetch returns its full text."""
        key = evidence_env.key("headed")
        await evidence_env.graph.add(documents=[make_headed_document(key)])

        result = await search_evidence(
            evidence_env.store,
            embedder,
            "lighthouse keeper fog",
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({key}),
        )

        assert result.status is EvidenceSearchStatus.OK
        hit = result.hits[0]
        assert hit.evidence_id.startswith("ev1:c:")
        outcomes = await fetch_evidence(
            evidence_env.store,
            [hit.evidence_id],
            scope=frozenset({key}),
            max_chars=8000,
        )
        assert outcomes[0].status is FetchStatus.OK
        assert outcomes[0].text is not None
        assert outcomes[0].text.startswith(HEADED_HEADING)
        assert hit.snippet == outcomes[0].text[: len(hit.snippet)]


class _FailingEmbedder(BagOfWordsEmbedder):
    """Embedder whose endpoint is unreachable."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Raise with an error that carries endpoint details."""
        raise RuntimeError("embedding endpoint refused connection at 10.0.0.5")


class TestHybridSearch:
    """Hybrid search fuses both legs and returns each passage once."""

    async def test_failed_semantic_leg_keeps_lexical_hits_with_a_fixed_message(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Lexical hits are returned as partial, and the failure text is generic."""
        result = await search_evidence(
            evidence_env.store,
            _FailingEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=frozenset(
                {evidence_env.keep, evidence_env.viber, evidence_env.harbor}
            ),
        )

        assert result.status is EvidenceSearchStatus.PARTIAL
        assert result.failures == [
            LegFailure(leg=EvidenceSearchLeg.SEMANTIC, message="search leg failed")
        ]
        positions = _gold_positions(result.hits)
        assert len(positions) == 1
        assert result.hits[positions[0]].legs == [EvidenceSearchLeg.LEXICAL]
        assert "10.0.0.5" not in result.model_dump_json()


class TestHybridSearchFusion:
    """Hybrid search fuses both legs and returns each passage once."""

    async def test_returns_the_gold_passage_once_with_both_legs(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """The gold chunk appears once and lists lexical and semantic as legs."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=frozenset(
                {evidence_env.keep, evidence_env.viber, evidence_env.harbor}
            ),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert len({hit.evidence_id for hit in result.hits}) == len(result.hits)
        positions = _gold_positions(result.hits)
        assert len(positions) == 1
        assert set(result.hits[positions[0]].legs) == {
            EvidenceSearchLeg.LEXICAL,
            EvidenceSearchLeg.SEMANTIC,
        }


class TestScope:
    """Search returns evidence only from the documents in scope."""

    async def test_scope_without_the_document_returns_no_gold_passage(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """With only the Viber notice in scope, no Keep passage is returned."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.viber}),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert result.hits
        assert {hit.document_key for hit in result.hits} == {evidence_env.viber}

    async def test_empty_scope_returns_no_hits_and_says_so(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """An empty scope is a distinct status, not a search of everything."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=frozenset(),
        )

        assert result.hits == []
        assert result.status is EvidenceSearchStatus.EMPTY_SCOPE

    async def test_returns_all_visible_matches_up_to_the_limit(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """Every visible lighthouse chunk of the one document is returned."""
        result = await search_evidence(
            evidence_env.store,
            embedder,
            "lighthouse",
            mode=EvidenceSearchMode.LEXICAL,
            limit=4,
            scope=frozenset({evidence_env.harbor}),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert len(result.hits) == 4
        assert {hit.document_key for hit in result.hits} == {evidence_env.harbor}


class TestIndexReadiness:
    """Search reports index_not_ready instead of an empty list."""

    @pytest.mark.parametrize("state", ["POPULATING", "missing"])
    async def test_lexical_reports_index_not_ready(
        self,
        evidence_env: EvidenceEnv,
        embedder: BagOfWordsEmbedder,
        monkeypatch: pytest.MonkeyPatch,
        state: str,
    ) -> None:
        """A full-text index that is not ONLINE gives the not-ready status."""
        store = evidence_env.store
        assert isinstance(store, Neo4jGraphStore)
        _hide_index(
            store,
            monkeypatch,
            name=fulltext_index_name("Chunk", ["text"]),
            state=state,
        )

        result = await search_evidence(
            store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )

        assert result.status is EvidenceSearchStatus.INDEX_NOT_READY
        assert result.index_state is IndexState.NOT_READY
        assert result.hits == []

    @pytest.mark.parametrize("state", ["POPULATING", "missing"])
    async def test_semantic_reports_index_not_ready(
        self,
        evidence_env: EvidenceEnv,
        embedder: BagOfWordsEmbedder,
        monkeypatch: pytest.MonkeyPatch,
        state: str,
    ) -> None:
        """A vector index that is not ONLINE gives the not-ready status."""
        store = evidence_env.store
        assert isinstance(store, Neo4jGraphStore)
        _hide_index(
            store,
            monkeypatch,
            name=vector_index_name("Chunk", "embedding"),
            state=state,
        )

        result = await search_evidence(
            store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.SEMANTIC,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )

        assert result.status is EvidenceSearchStatus.INDEX_NOT_READY
        assert result.index_state is IndexState.NOT_READY
        assert result.hits == []


class TestHistory:
    """Search returns only current text after a document update."""

    async def test_after_update_only_new_text_is_found_and_limit_is_filled(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """Superseded chunks do not take result slots; the new chunks fill the limit."""
        await evidence_env.graph.update(evidence_env.harbor, text=HARBOR_TEXT_V2)

        result: EvidenceSearchResult = await search_evidence(
            evidence_env.store,
            embedder,
            "lighthouse",
            mode=EvidenceSearchMode.LEXICAL,
            limit=3,
            scope=frozenset({evidence_env.harbor}),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert len(result.hits) == 3
        current_hash = sha256_of(HARBOR_TEXT_V2)
        assert {hit.content_hash for hit in result.hits} == {current_hash}


class TestSearchFailures:
    """Read errors and oversized requests stay inside search's contract."""

    async def test_index_state_read_error_returns_a_failed_result(
        self,
        evidence_env: EvidenceEnv,
        embedder: BagOfWordsEmbedder,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed index read gives the failed status and no error text."""
        store = evidence_env.store
        original = store.execute_read

        async def execute_read(
            query: str,
            parameters: Mapping[str, Any] | None = None,
            *,
            timeout: float | None = None,
        ) -> list[dict[str, Any]]:
            if "SHOW INDEXES" in query:
                raise RuntimeError("connection reset by peer at 10.0.0.9")
            return await original(query, parameters, timeout=timeout)

        monkeypatch.setattr(store, "execute_read", execute_read)

        result = await search_evidence(
            store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )

        assert result.status is EvidenceSearchStatus.FAILED
        assert result.hits == []
        assert "10.0.0.9" not in result.model_dump_json()

    async def test_limit_above_the_candidate_ceiling_never_sends_a_larger_k(
        self,
        evidence_env: EvidenceEnv,
        embedder: BagOfWordsEmbedder,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A limit of 1500 is served with candidate counts of at most 1000."""
        store = evidence_env.store
        original = store.execute_read
        requested: list[int] = []

        async def execute_read(
            query: str,
            parameters: Mapping[str, Any] | None = None,
            *,
            timeout: float | None = None,
        ) -> list[dict[str, Any]]:
            if parameters and "k" in parameters:
                requested.append(int(parameters["k"]))
            return await original(query, parameters, timeout=timeout)

        monkeypatch.setattr(store, "execute_read", execute_read)

        result = await search_evidence(
            store,
            embedder,
            "lighthouse",
            mode=EvidenceSearchMode.LEXICAL,
            limit=1500,
            scope=frozenset({evidence_env.harbor}),
        )

        assert requested
        assert max(requested) <= 1000
        assert result.status is EvidenceSearchStatus.OK
        assert len(result.hits) == 4

    async def test_index_with_the_right_name_but_another_label_is_not_ready(
        self,
        evidence_env: EvidenceEnv,
        embedder: BagOfWordsEmbedder,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A same-named index on another label is not used for search."""
        store = evidence_env.store
        assert isinstance(store, Neo4jGraphStore)
        original = store.execute_read
        name = fulltext_index_name("Chunk", ["text"])

        async def execute_read(
            query: str,
            parameters: Mapping[str, Any] | None = None,
            *,
            timeout: float | None = None,
        ) -> list[dict[str, Any]]:
            rows = await original(query, parameters, timeout=timeout)
            if "SHOW INDEXES" not in query:
                return rows
            return [
                {**row, "labelsOrTypes": ["Document"]} if row["name"] == name else row
                for row in rows
            ]

        monkeypatch.setattr(store, "execute_read", execute_read)

        result = await search_evidence(
            store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )

        assert result.status is EvidenceSearchStatus.INDEX_NOT_READY
        assert result.index_state is IndexState.NOT_READY


class TestReAddedDocument:
    """Adding a key again with new text hides the earlier text from search."""

    async def test_earlier_text_is_not_searchable_after_a_second_add(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """Only the text of the latest add is searchable."""
        replacement = (
            "The orchard ledger lists apples, pears and plums for the autumn fair."
        )
        await evidence_env.graph.add(
            documents=[make_document(evidence_env.keep, replacement)]
        )

        old = await search_evidence(
            evidence_env.store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )
        new = await search_evidence(
            evidence_env.store,
            embedder,
            "orchard ledger apples",
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=frozenset({evidence_env.keep}),
        )

        assert _gold_positions(old.hits) == []
        assert new.hits
        assert {hit.content_hash for hit in new.hits} == {sha256_of(replacement)}


class TestTelemetry:
    """Full-text search terms do not reach exported span attributes."""

    async def test_search_terms_are_not_exported_as_span_attributes(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """No span attribute carries the words the user searched for."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        store = Neo4jGraphStore(tracer=provider.get_tracer("agrag-test"))
        await store.connect()
        try:
            await search_evidence(
                store,
                embedder,
                "lighthouse",
                mode=EvidenceSearchMode.LEXICAL,
                limit=4,
                scope=frozenset({evidence_env.harbor}),
            )
        finally:
            await store.close()

        values = [
            str(value)
            for span in exporter.get_finished_spans()
            for value in (span.attributes or {}).values()
        ]
        assert values
        assert not any("lighthouse" in value for value in values)


class TestStaleHitsFillTheWindow:
    """Hidden full-text hits never stop paging while live hits remain below them."""

    async def test_live_hits_below_out_of_scope_deleted_and_superseded_hits(
        self, evidence_env: EvidenceEnv, embedder: BagOfWordsEmbedder
    ) -> None:
        """The live passage is found even though many higher-ranked hits are hidden."""
        decoy_text = "keep upload activity database " * 2
        out_of_scope = [evidence_env.key(f"out-{i}") for i in range(30)]
        deleted = [evidence_env.key(f"deleted-{i}") for i in range(30)]
        superseded = [evidence_env.key(f"superseded-{i}") for i in range(30)]
        live = evidence_env.key("live")
        await evidence_env.graph.add(
            documents=[
                make_document(key, decoy_text)
                for key in [*out_of_scope, *deleted, *superseded]
            ]
            + [
                make_document(
                    live,
                    "We keep and upload your activity to our database. The "
                    "lighthouse crew logs the weather in a long ledger of quiet "
                    "nights for the harbor keeper.",
                )
            ]
        )
        for key in deleted:
            await evidence_env.graph.delete_document(key)
        for key in superseded:
            await evidence_env.graph.update(key, text="lighthouse harbor gasket")

        result = await search_evidence(
            evidence_env.store,
            embedder,
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=3,
            scope=frozenset({live, *superseded}),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert result.truncated is False
        assert result.hits
        assert {hit.document_key for hit in result.hits} == {live}
