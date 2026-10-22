"""Integration tests for the MCP server tools over an in-memory client.

The tools run against the authored evidence corpus in the shared Neo4j test
database, with the bag-of-words embedder. Each test writes its own corpus under
unique document keys. The expected results come from the direct evidence
functions and from the authored text, never from the server code.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.evidence import (
    CitationResult,
    CitationVerdict,
    EvidenceSearchHit,
    EvidenceSearchLeg,
    EvidenceSearchMode,
    EvidenceSearchResult,
    EvidenceSearchStatus,
    FetchOutcome,
    FetchResult,
    FetchStatus,
    LegFailure,
)
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.embedding.base import Embedder
from agrag.evidence import check_citations, fetch_evidence, search_evidence
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings
from agrag.mcp_server.server import build_server
from agrag.mcp_server.settings import McpServerSettings
from tests.integration.retrieval.evidence._corpus import (
    GOLD_SENTENCE,
    HARBOR_TEXT,
    KEEP_TEXT,
    VECTOR_DIMENSIONS,
    VIBER_TEXT,
    BagOfWordsEmbedder,
    locate,
    make_document,
    span_evidence_id,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


_LEXICAL_QUERY = "keep upload activity database"
_HYBRID_QUERY = "do you keep and upload my activity to your database"
_COUNT_QUERY = (
    "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
    "OPTIONAL MATCH (d)-[r]->(c) "
    "RETURN count(DISTINCT d) AS documents, count(DISTINCT c) AS targets, "
    "count(r) AS edges"
)
_STORE_UNAVAILABLE = "evidence store unavailable"
_GOLD_START, _GOLD_END = locate(KEEP_TEXT, GOLD_SENTENCE)


class _HookedStore(Neo4jGraphStore):
    """A Neo4j store whose reads can be delayed, failed or filtered.

    Reads and connections go through the wrapped store, which the test corpus
    was written with. These evidence tests do not wrap the memory write paths.

    Args:
        inner: The store that answers the reads.
        before_read: Awaited before each read. It can block or raise.
        hide_lexical_index: When True, SHOW INDEXES omits the chunk full-text
            index, as if it were missing.
        vector_dimensions: The dimension reported by the vector index metadata,
            or None to report that the vector index is absent.
    """

    def __init__(
        self,
        inner: Neo4jGraphStore,
        *,
        before_read: Callable[[], Awaitable[None]] | None = None,
        hide_lexical_index: bool = False,
        vector_dimensions: int | None = VECTOR_DIMENSIONS,
    ) -> None:
        super().__init__(settings=Neo4jSettings())
        self._inner = inner
        self._before_read = before_read
        self.vector_dimensions = vector_dimensions
        self._hidden_index = (
            fulltext_index_name(CHUNK_LABEL, ["text"]) if hide_lexical_index else None
        )

    async def connect(self) -> None:
        """Connect the wrapped store."""
        await self._inner.connect()

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run a read on the wrapped store, after the hook."""
        if self._before_read is not None:
            await self._before_read()
        rows = await self._inner.execute_read(query, parameters, timeout=timeout)
        if "SHOW INDEXES" not in query:
            return rows
        name = vector_index_name(CHUNK_LABEL, "embedding")
        if self.vector_dimensions is None:
            rows = [row for row in rows if row["name"] != name]
        else:
            rows = [
                {
                    **row,
                    "options": {
                        "indexConfig": {"vector.dimensions": self.vector_dimensions}
                    },
                }
                if row["name"] == name
                else row
                for row in rows
            ]
        return [row for row in rows if row["name"] != self._hidden_index]


class _BlockFirstRead:
    """Blocks the first read until the task is cancelled, then lets reads pass.

    The first read signals ``entered`` before it waits, so a test knows the
    call is in flight without a sleep.
    """

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self._started = False

    async def __call__(self) -> None:
        """Block the first call forever, and return at once for later calls."""
        if self._started:
            return
        self._started = True
        self.entered.set()
        await asyncio.Event().wait()


def _settings(env: EvidenceEnv, **overrides: int | float) -> McpServerSettings:
    """Return settings whose scope holds the Keep and Harbor documents."""
    return McpServerSettings(
        scope_document_keys=f"{env.keep},{env.harbor}",
        _env_file=None,
        **overrides,
    )


def _server(
    store: Neo4jGraphStore,
    env: EvidenceEnv,
    *,
    embedder: Embedder | None = None,
    **overrides: int | float,
) -> Any:
    """Build the server over a store, with the test scope and an embedder.

    The embedder defaults to the bag-of-words fake, which matches the index.
    """
    return build_server(
        store, embedder or BagOfWordsEmbedder(), _settings(env, **overrides)
    )


class _FiveDimensionEmbedder(BagOfWordsEmbedder):
    """The bag-of-words fake with one extra dimension than the Chunk index.

    Vectors of this embedder cannot match the stored vectors, so a server that
    checks the dimension must refuse the semantic leg before any search runs.
    """

    async def dimensions(self) -> int:
        """Return five, one more than the index."""
        return VECTOR_DIMENSIONS + 1

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the bag-of-words vectors with one zero padded dimension."""
        vectors = await super().embed(texts)
        return [[*vector, 0.0] for vector in vectors]


_EMBEDDING_MISMATCH = (
    "the query embedding model does not match the stored vectors; set the same "
    "EMBEDDING_* settings that ingestion used or use lexical mode"
)


async def _structured(client: Client, name: str, arguments: dict[str, Any]) -> Any:
    """Call a tool and return its structured content, failing on a tool error."""
    result = await client.call_tool(name, arguments)
    assert not result.is_error, result.content
    return result.structured_content


async def _counts(env: EvidenceEnv) -> tuple[int, int, int]:
    """Return the document, target and edge counts of the test corpus."""
    [row] = await env.store.execute_read(_COUNT_QUERY, {"prefix": env.key("")})
    return row["documents"], row["targets"], row["edges"]


def _gold_span_id(env: EvidenceEnv) -> str:
    """Return the span id of the Keep gold sentence."""
    return span_evidence_id(env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END)


class TestToolListing:
    """The server lists scoped evidence tools and their schemas."""

    async def test_lists_evidence_tools_without_a_scope_argument(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """List evidence tools with read-only annotations and no scope argument."""
        async with Client(_server(evidence_env.store, evidence_env)) as client:
            listing = await client.list_tools()

        names = sorted(tool.name for tool in listing.tools)
        assert {
            "check_citations",
            "explore_relationships",
            "fetch_evidence",
            "entity_search",
            "navigate_document_tree",
            "search_evidence",
        } <= set(names)
        for tool in listing.tools:
            assert tool.input_schema is not None
            assert tool.output_schema is not None
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint is True
            assert "scope" not in tool.input_schema["properties"]

    async def test_lists_memory_reads_when_project_and_agent_are_set(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Add the project-scoped memory reads to the evidence tools."""
        settings = _settings(evidence_env).model_copy(
            update={"project_id": "project-a", "agent_id": "assistant-a"}
        )
        server = build_server(evidence_env.store, BagOfWordsEmbedder(), settings)
        async with Client(server) as client:
            listing = await client.list_tools()

        names = sorted(tool.name for tool in listing.tools)
        assert names == [
            "check_citations",
            "entity_search",
            "explore_relationships",
            "fetch_event",
            "fetch_evidence",
            "get_decision",
            "get_task",
            "list_conflicts",
            "list_decisions",
            "list_decisions_for_review",
            "list_events",
            "list_steps",
            "list_support_history",
            "navigate_document_tree",
            "search_decisions",
            "search_evidence",
        ]


class TestEquivalenceWithDirectCalls:
    """Tool results equal the direct evidence functions on the same corpus."""

    async def test_fetched_source_links_preserve_ids_and_response_limits(
        self, evidence_env: EvidenceEnv, tmp_path: Path
    ) -> None:
        """Stored source metadata reaches both MCP encodings, not dropped fetches."""
        env = evidence_env
        for key, uri, title in [
            (env.keep, "https://example.org/privacy", "Privacy notice"),
            (env.harbor, "/reports/harbor.txt", "Harbor log"),
        ]:
            text = (KEEP_TEXT if key == env.keep else HARBOR_TEXT) + "\nSource edition."
            document = make_document(key, text).model_copy(
                update={"uri": uri, "title": title}
            )
            await env.graph.add(documents=[document])
        ids = [
            span_evidence_id(
                env.keep, KEEP_TEXT + "\nSource edition.", _GOLD_START, _GOLD_END
            ),
            span_evidence_id(env.harbor, HARBOR_TEXT + "\nSource edition.", 0, 20),
        ]
        async with Client(_server(env.store, env)) as client:
            response = await client.call_tool("fetch_evidence", {"evidence_ids": ids})
            assert not response.is_error
            structured = response.structured_content
            assert structured is not None
            remote, local = structured["outcomes"]
            assert remote["title"] == "Privacy notice"
            assert remote["uri"] == "https://example.org/privacy"
            assert remote["citation_markdown"] == (
                "[Privacy notice](https://example.org/privacy)"
            )
            assert local["uri"] is None
            assert local["citation_markdown"] == "Harbor log"
            assert "/reports/harbor.txt" not in _text(response)
            assert "/reports/harbor.txt" not in response.model_dump_json()
            assert remote["citation_markdown"] in _text(response)
            assert remote["evidence_id"] == ids[0]
            (tmp_path / "source-citations.json").write_text(
                response.model_dump_json(by_alias=True, indent=2)
            )

        budget = 2 * len(FetchResult.model_validate(structured).model_dump_json()) - 100
        async with Client(_server(env.store, env, max_response_chars=budget)) as client:
            capped = await _structured(client, "fetch_evidence", {"evidence_ids": ids})
            assert capped["truncated"] is True
            assert len(capped["outcomes"]) == 1
            checked = await _structured(
                client, "check_citations", {"evidence_ids": ids}
            )
            assert [item["verdict"] for item in checked["checks"]] == [
                "valid",
                "not_fetched",
            ]

    @pytest.mark.parametrize(
        ("mode", "query"),
        [
            (EvidenceSearchMode.LEXICAL, _LEXICAL_QUERY),
            (EvidenceSearchMode.HYBRID, _HYBRID_QUERY),
        ],
    )
    async def test_search_result_equals_direct_search_evidence(
        self, evidence_env: EvidenceEnv, mode: EvidenceSearchMode, query: str
    ) -> None:
        """Return the same hits and status as a direct search call."""
        env = evidence_env
        scope = _settings(env).scope
        direct = await search_evidence(
            env.store,
            BagOfWordsEmbedder(),
            query,
            mode=mode,
            limit=5,
            scope=scope,
        )

        async with Client(_server(env.store, env)) as client:
            structured = await _structured(
                client,
                "search_evidence",
                {"query": query, "mode": mode.value, "limit": 5},
            )

        assert direct.status is EvidenceSearchStatus.OK
        result = EvidenceSearchResult.model_validate(structured)
        assert result.hits
        assert all(hit.score > 0 for hit in result.hits)
        # Parallel corpus writes change full-text scores between the two calls.
        exclude = {"hits": {"__all__": {"score"}}}
        assert result.model_dump(exclude=exclude) == direct.model_dump(exclude=exclude)

    async def test_fetch_returns_gold_text_and_treats_out_of_scope_like_missing(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Return the gold text, and treat an out-of-scope id like a missing one."""
        env = evidence_env
        scope = _settings(env).scope
        viber_id = span_evidence_id(env.viber, VIBER_TEXT, 0, 40)
        missing_id = span_evidence_id(env.key("missing"), KEEP_TEXT, 0, 40)
        ids = [_gold_span_id(env), viber_id, missing_id]
        direct = await fetch_evidence(env.store, ids, scope=scope, max_chars=10_000)

        async with Client(_server(env.store, env)) as client:
            structured = await _structured(
                client, "fetch_evidence", {"evidence_ids": ids}
            )

        outcomes = FetchResult.model_validate(structured).outcomes
        assert outcomes == direct
        assert outcomes[0].status is FetchStatus.OK
        assert outcomes[0].text == GOLD_SENTENCE
        assert outcomes[1].status is FetchStatus.UNAVAILABLE
        assert outcomes[2].status is FetchStatus.UNAVAILABLE
        assert _without_id(outcomes[1]) == _without_id(outcomes[2])

    async def test_citations_follow_what_this_server_fetched(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Trace citations only against the ids that this server fetched in full."""
        env = evidence_env
        scope = _settings(env).scope
        gold = _gold_span_id(env)
        inner_span = span_evidence_id(
            env.keep, KEEP_TEXT, _GOLD_START + 5, _GOLD_START + 20
        )
        wider_span = span_evidence_id(env.keep, KEEP_TEXT, 0, len(KEEP_TEXT))
        harbor_span = span_evidence_id(env.harbor, HARBOR_TEXT, 0, 10)
        viber_span = span_evidence_id(env.viber, VIBER_TEXT, 0, 40)
        cited = [gold, inner_span, wider_span, harbor_span, viber_span]

        async with Client(_server(env.store, env)) as client:
            await _structured(client, "fetch_evidence", {"evidence_ids": [gold]})
            structured = await _structured(
                client, "check_citations", {"evidence_ids": cited}
            )

        direct = await check_citations(cited, [gold], scope=scope)
        verdicts = CitationResult.model_validate(structured).checks
        assert verdicts == direct
        assert [check.verdict for check in verdicts] == [
            CitationVerdict.VALID,
            CitationVerdict.VALID,
            CitationVerdict.NOT_FETCHED,
            CitationVerdict.NOT_FETCHED,
            CitationVerdict.UNAVAILABLE,
        ]

    async def test_a_new_server_starts_with_an_empty_fetched_record(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Start a new server process with no fetched ids on record."""
        env = evidence_env
        gold = _gold_span_id(env)
        async with Client(_server(env.store, env)) as client:
            await _structured(client, "fetch_evidence", {"evidence_ids": [gold]})

        async with Client(_server(env.store, env)) as client:
            structured = await _structured(
                client, "check_citations", {"evidence_ids": [gold]}
            )

        verdicts = CitationResult.model_validate(structured).checks
        assert verdicts[0].verdict is CitationVerdict.NOT_FETCHED


class TestSharedEvidenceTools:
    """Entity and navigation tools keep all reads inside configured scope."""

    async def test_entity_and_navigation_calls_keep_trusted_scope(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Return scoped entity support and hide a valid out-of-scope passage."""
        env = evidence_env
        outside_id = span_evidence_id(env.viber, VIBER_TEXT, 0, 40)

        async with Client(_server(env.store, env)) as client:
            entities = await client.call_tool(
                "entity_search",
                {"query": "activity", "mode": "lexical", "limit": 5},
            )
            assert not entities.is_error, entities.content
            entity_result = entities.structured_content
            assert all(
                passage["document_key"] in _settings(env).scope
                for hit in entity_result["hits"]
                for passage in hit["support"]
            )

            navigation = await client.call_tool(
                "navigate_document_tree",
                {"evidence_id": outside_id, "relation": "next", "limit": 5},
            )
            assert not navigation.is_error, navigation.content
            assert navigation.structured_content["status"] == "unavailable"

            exploration = await client.call_tool(
                "explore_relationships", {"entity_id": "not-an-entity-id"}
            )
            assert not exploration.is_error, exploration.content
            assert exploration.structured_content["status"] == "malformed"


class TestOutputLimits:
    """Server caps apply whatever the caller asks for, and results say so."""

    async def test_limit_above_the_maximum_is_capped_and_marked_truncated(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Cap a search limit above the maximum and mark the result truncated."""
        env = evidence_env
        async with Client(_server(env.store, env, max_hits=2)) as client:
            structured = await _structured(
                client,
                "search_evidence",
                {"query": "privacy notice data", "mode": "lexical", "limit": 50},
            )

        result = EvidenceSearchResult.model_validate(structured)
        assert len(result.hits) == 2
        assert result.truncated is True

    async def test_fetched_text_above_the_maximum_is_cut_and_marked(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Cut fetched text to the maximum and mark the outcome truncated."""
        env = evidence_env
        async with Client(_server(env.store, env, max_fetch_chars=20)) as client:
            structured = await _structured(
                client,
                "fetch_evidence",
                {"evidence_ids": [_gold_span_id(env)], "max_chars": 1_000_000},
            )

        [outcome] = FetchResult.model_validate(structured).outcomes
        assert outcome.status is FetchStatus.TRUNCATED
        assert outcome.text == GOLD_SENTENCE[:20]

    async def test_too_many_ids_is_a_correctable_tool_error(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Reject a fetch with more ids than the maximum with a tool error."""
        env = evidence_env
        ids = [_gold_span_id(env)] * 3
        async with Client(_server(env.store, env, max_fetch_ids=2)) as client:
            result = await client.call_tool("fetch_evidence", {"evidence_ids": ids})

        assert result.is_error is True
        assert "at most 2 evidence ids per call" in _text(result)

    async def test_result_over_the_size_limit_drops_hits_and_marks_truncated(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Drop trailing hits when the serialized result exceeds the size limit."""
        env = evidence_env
        arguments = {"query": "privacy notice data", "mode": "lexical", "limit": 10}
        async with Client(_server(env.store, env)) as client:
            full = EvidenceSearchResult.model_validate(
                await _structured(client, "search_evidence", arguments)
            )
        full_size = 2 * len(full.model_dump_json())

        async with Client(
            _server(env.store, env, max_response_chars=full_size // 2)
        ) as client:
            structured = await _structured(client, "search_evidence", arguments)

        capped = EvidenceSearchResult.model_validate(structured)
        assert len(capped.hits) < len(full.hits)
        assert capped.truncated is True
        assert 2 * len(capped.model_dump_json()) <= full_size // 2


@pytest.mark.neo4j_only
class TestStoreFailures:
    """Store failures give fixed messages, and index gaps stay data."""

    async def test_store_error_gives_fixed_message_and_no_details(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Report a failed store with the fixed message and no store details."""
        env = evidence_env

        async def fail() -> None:
            raise RuntimeError("bolt password leaked in the driver message")

        store = _HookedStore(env.store, before_read=fail)
        async with Client(_server(store, env)) as client:
            result = await client.call_tool(
                "search_evidence", {"query": _LEXICAL_QUERY, "mode": "lexical"}
            )

        assert result.is_error is True
        assert (
            _text(result)
            == f"Error executing tool search_evidence: {_STORE_UNAVAILABLE}"
        )
        assert "leaked" not in str(result.structured_content)

    async def test_missing_index_reports_index_not_ready_not_an_empty_list(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Report a missing index as index_not_ready, not as no match."""
        env = evidence_env
        store = _HookedStore(env.store, hide_lexical_index=True)
        async with Client(_server(store, env)) as client:
            structured = await _structured(
                client,
                "search_evidence",
                {"query": _LEXICAL_QUERY, "mode": "lexical"},
            )

        result = EvidenceSearchResult.model_validate(structured)
        assert result.status is EvidenceSearchStatus.INDEX_NOT_READY


@pytest.mark.neo4j_only
class TestEmbeddingModelMismatch:
    """A query embedder that differs from the stored vectors never searches them."""

    async def test_index_changes_take_effect_without_restarting_the_server(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Observe a missing, created, replaced, and repaired vector index."""
        env = evidence_env
        store = _HookedStore(env.store, vector_dimensions=None)
        async with Client(_server(store, env)) as client:
            for mode in ("semantic", "hybrid"):
                structured = await _structured(
                    client, "search_evidence", {"query": _HYBRID_QUERY, "mode": mode}
                )
                result = EvidenceSearchResult.model_validate(structured)
                assert result.status is EvidenceSearchStatus.INDEX_NOT_READY
                assert result.failures == []

            store.vector_dimensions = VECTOR_DIMENSIONS
            structured = await _structured(
                client, "search_evidence", {"query": _HYBRID_QUERY, "mode": "semantic"}
            )
            assert (
                EvidenceSearchResult.model_validate(structured).status
                is EvidenceSearchStatus.OK
            )

            store.vector_dimensions = VECTOR_DIMENSIONS + 1
            refused = await client.call_tool(
                "search_evidence", {"query": _HYBRID_QUERY, "mode": "semantic"}
            )
            assert refused.is_error is True
            assert _EMBEDDING_MISMATCH in _text(refused)
            structured = await _structured(
                client, "search_evidence", {"query": _LEXICAL_QUERY, "mode": "hybrid"}
            )
            result = EvidenceSearchResult.model_validate(structured)
            assert result.status is EvidenceSearchStatus.PARTIAL
            assert result.hits
            assert all(hit.legs == [EvidenceSearchLeg.LEXICAL] for hit in result.hits)

            store.vector_dimensions = VECTOR_DIMENSIONS
            structured = await _structured(
                client, "search_evidence", {"query": _HYBRID_QUERY, "mode": "semantic"}
            )
            result = EvidenceSearchResult.model_validate(structured)
            assert result.status is EvidenceSearchStatus.OK
            assert result.hits
            assert all(hit.legs == [EvidenceSearchLeg.SEMANTIC] for hit in result.hits)

    async def test_semantic_search_refuses_the_mismatched_embedder(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Refuse a semantic search with a fixed tool error."""
        env = evidence_env
        server = _server(env.store, env, embedder=_FiveDimensionEmbedder())
        async with Client(server) as client:
            result = await client.call_tool(
                "search_evidence", {"query": _HYBRID_QUERY, "mode": "semantic"}
            )

        assert result.is_error is True
        assert _text(result) == (
            f"Error executing tool search_evidence: {_EMBEDDING_MISMATCH}"
        )

    async def test_hybrid_search_returns_lexical_hits_and_reports_the_leg(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Return the lexical hits with the semantic leg reported as a failure."""
        env = evidence_env
        server = _server(env.store, env, embedder=_FiveDimensionEmbedder())
        async with Client(server) as client:
            structured = await _structured(
                client,
                "search_evidence",
                {"query": _LEXICAL_QUERY, "mode": "hybrid", "limit": 5},
            )
        lexical = await search_evidence(
            env.store,
            _FiveDimensionEmbedder(),
            _LEXICAL_QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=_settings(env).scope,
        )

        result = EvidenceSearchResult.model_validate(structured)
        assert result.status is EvidenceSearchStatus.PARTIAL
        assert result.failures == [
            LegFailure(leg=EvidenceSearchLeg.SEMANTIC, message=_EMBEDDING_MISMATCH)
        ]
        assert result.hits
        assert [hit.evidence_id for hit in result.hits] == [
            hit.evidence_id for hit in lexical.hits
        ]
        assert all(hit.legs == [EvidenceSearchLeg.LEXICAL] for hit in result.hits)

    async def test_lexical_search_is_unaffected_by_the_mismatched_embedder(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Answer a lexical search the same as a direct lexical search."""
        env = evidence_env
        server = _server(env.store, env, embedder=_FiveDimensionEmbedder())
        async with Client(server) as client:
            structured = await _structured(
                client,
                "search_evidence",
                {"query": _LEXICAL_QUERY, "mode": "lexical", "limit": 5},
            )
        direct = await search_evidence(
            env.store,
            _FiveDimensionEmbedder(),
            _LEXICAL_QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=_settings(env).scope,
        )

        result = EvidenceSearchResult.model_validate(structured)
        assert result.hits
        assert all(hit.score > 0 for hit in result.hits)
        # Parallel corpus writes change full-text scores between the two calls.
        exclude = {"hits": {"__all__": {"score"}}}
        assert result.model_dump(exclude=exclude) == direct.model_dump(exclude=exclude)

    async def test_semantic_search_works_with_the_matching_embedder(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Run a semantic search with an embedder that matches the index."""
        env = evidence_env
        async with Client(_server(env.store, env)) as client:
            structured = await _structured(
                client,
                "search_evidence",
                {"query": _HYBRID_QUERY, "mode": "semantic", "limit": 5},
            )

        result = EvidenceSearchResult.model_validate(structured)
        assert result.status is EvidenceSearchStatus.OK
        assert result.failures == []
        assert result.hits
        assert all(EvidenceSearchLeg.SEMANTIC in hit.legs for hit in result.hits)

    async def test_citation_checks_fit_the_response_budget(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Drop trailing citation checks and mark them when the budget is tight."""
        env = evidence_env
        cited_ids = ["x" * 200, "y" * 200]
        async with Client(
            _server(env.store, env, max_response_chars=300, max_fetch_ids=2)
        ) as client:
            structured = await _structured(
                client, "check_citations", {"evidence_ids": cited_ids}
            )

        result = CitationResult.model_validate(structured)
        assert result.truncated is True
        assert 2 * len(result.model_dump_json()) <= 300

    async def test_too_small_response_budget_returns_a_tool_error(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Do not return even an empty result envelope above the configured cap."""
        env = evidence_env
        async with Client(_server(env.store, env, max_response_chars=1)) as client:
            result = await client.call_tool(
                "search_evidence", {"query": "unknown", "mode": "lexical"}
            )

        assert result.is_error is True
        assert "too small for an empty result" in _text(result)


@pytest.mark.neo4j_only
class TestCancellation:
    """A cancelled search leaves the graph and the next call unaffected."""

    async def test_cancelled_search_changes_no_counts_and_the_next_call_answers(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Keep the graph unchanged and keep serving after a cancelled search."""
        env = evidence_env
        block = _BlockFirstRead()
        store = _HookedStore(env.store, before_read=block)
        arguments = {"query": _LEXICAL_QUERY, "mode": "lexical"}
        before = await _counts(env)

        async with Client(_server(store, env)) as client:
            call = asyncio.create_task(client.call_tool("search_evidence", arguments))
            await asyncio.wait_for(block.entered.wait(), timeout=30)
            call.cancel()
            with suppress(asyncio.CancelledError):
                await call

            assert await _counts(env) == before
            structured = await _structured(client, "search_evidence", arguments)

        assert EvidenceSearchResult.model_validate(structured).hits


def _without_id(outcome: FetchOutcome) -> dict[str, Any]:
    """Return an outcome without its requested id."""
    return outcome.model_dump(exclude={"evidence_id"})


def _text(result: Any) -> str:
    """Return the text of the first content block of a tool result."""
    return result.content[0].text


__all__ = ["EvidenceSearchHit"]
