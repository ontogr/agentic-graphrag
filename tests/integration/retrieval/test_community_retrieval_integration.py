"""Integration tests for community retrieval against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``).
"""

import asyncio
import importlib.util
from collections.abc import AsyncGenerator, Sequence
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.common.data_models.community import (
    COMMUNITY_LABEL,
    MEMBER_OF_RELATION,
    Community,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.retrieval.community_context import community_context
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import HYBRID_RERANKED, THEMATIC, Recipe
from agrag.retrieval.retrievers.community import CommunityRetriever
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Embedder returning deterministic vectors for testing."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a deterministic vector per text.

        Each text gets a unique vector based on its hash.
        """
        vectors: list[list[float]] = []
        for text in texts:
            h = hash(text) % 1000
            vectors.append(
                [
                    float(h % 10) / 10.0,
                    float((h // 10) % 10) / 10.0,
                    float((h // 100) % 10) / 10.0,
                    0.5,
                ]
            )
        return vectors


@pytest.mark.integration
@pytest.mark.enable_socket
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.xdist_group(name="community_label")
class TestCommunityRetrievalIntegration:
    """Community retrieval against a real Neo4j graph store.

    Shares an ``xdist_group`` with the ``tests/integration/cypher``
    community tests: several tests here write Community nodes and query
    the shared native Community vector index directly, which a
    concurrently-running test elsewhere (writing or deleting its own
    Community nodes against the same index) can perturb. Keeping every
    Community-writing test class on one worker avoids that.
    """

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store for each test.

        ``community_ids`` starts empty and ``_seed_communities`` appends
        to it, so teardown deletes exactly this test's own Community
        nodes by id instead of the shared ``Community`` label -- other
        integration tests write Community nodes to the same database and
        may be running concurrently.
        """
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.embedder = _FixedEmbedder()
        self.settings = RetrievalSettings(
            entity_labels=[self.label],
            entity_top_k=10,
            chunk_top_k=10,
            community_top_k=5,
        )
        self.community_ids: list[UUID] = []
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        if self.community_ids:
            await self.store.execute_write(
                f"MATCH (n:{COMMUNITY_LABEL}) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(cid) for cid in self.community_ids]},
            )
        await self.store.close()

    async def _wait_for_index(
        self, *, label: str, vector: list[float], expected_id: UUID
    ) -> None:
        """Wait until ``label``'s vector index returns the seeded node.

        Neo4j populates and updates a vector index asynchronously, so a
        search issued right after the nodes are written can miss them. Every
        seed helper waits here, so each test's own vector searches start
        from a populated index rather than retrying their assertions.

        Membership of ``expected_id`` is checked rather than a non-empty
        result, because the Community index is shared across tests in this
        worker: a leftover entry from a just-deleted test would otherwise
        satisfy the wait while the node this test just wrote is still
        invisible. ``limit`` is set well above the handful of records any
        one test seeds so such leftovers cannot crowd the seeded node out.
        """
        for _ in range(10):
            hits = await self.store.vector_search(
                label=label,
                vector_property="embedding",
                query_vector=vector,
                limit=100,
            )
            if any(hit.id == expected_id for hit in hits):
                return
            await asyncio.sleep(1)

    async def _seed_entities(self, names: list[str]) -> list[Entity]:
        """Write entities with embeddings to the store."""
        entities: list[Entity] = []
        for name in names:
            ent = Entity(id=uuid4(), label="Person", name=name)
            ent.embedding = await self.embedder.embed_one(name)
            entities.append(ent)

        records = [
            NodeRecord(
                id=ent.id,
                labels=[self.label],
                properties={
                    "name": ent.name,
                    "merge_key": ent.merge_key,
                    "merged_from": [],
                    "merge_count": 1,
                    "source_chunk_ids": [],
                    "embedding": ent.embedding,
                    "created_at": ent.created_at.isoformat(),
                },
            )
            for ent in entities
        ]
        await self.store.upsert_nodes(self.label, records)
        await self.store.ensure_vector_index(
            label=self.label,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )
        first_embedding = entities[0].embedding if entities else None
        if first_embedding:
            await self._wait_for_index(
                label=self.label,
                vector=first_embedding,
                expected_id=entities[0].id,
            )
        return entities

    async def _seed_communities(self, communities: list[Community]) -> list[Community]:
        """Write communities and MEMBER_OF edges to the store."""
        self.community_ids.extend(comm.id for comm in communities)
        for comm in communities:
            if comm.embedding is None:
                comm.embedding = await self.embedder.embed_one(comm.embedding_text)

        records = [comm.to_node_record() for comm in communities]
        await self.store.upsert_nodes(COMMUNITY_LABEL, records)
        await self.store.ensure_vector_index(
            label=COMMUNITY_LABEL,
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )
        first_embedding = communities[0].embedding if communities else None
        if first_embedding:
            await self._wait_for_index(
                label=COMMUNITY_LABEL,
                vector=first_embedding,
                expected_id=communities[0].id,
            )

        relations: list[RelationRecord] = []
        for comm in communities:
            for member_id in comm.member_ids:
                relations.append(
                    RelationRecord(
                        id=uuid4(),
                        type=MEMBER_OF_RELATION,
                        start_id=member_id,
                        end_id=comm.id,
                        properties={},
                    )
                )
        if relations:
            await self.store.upsert_relations(relations)
        return communities

    async def _seed_relation(
        self, source_id: UUID, target_id: UUID, rel_type: str = "KNOWS"
    ) -> None:
        """Write a single relation between two entities."""
        await self.store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type=rel_type,
                    start_id=source_id,
                    end_id=target_id,
                    properties={"source_chunk_ids": []},
                )
            ]
        )

    async def test_community_context_top_k(self) -> None:
        """Top-k caps results and highest overlap ranks first."""
        entities = await self._seed_entities(["Alice", "Bob", "Charlie"])
        comm_high = Community(
            id=uuid4(),
            title="High",
            summary="High overlap",
            rating=5.0,
            rating_explanation="e",
            member_ids=[entities[0].id, entities[1].id],
        )
        comm_low = Community(
            id=uuid4(),
            title="Low",
            summary="Low overlap",
            rating=5.0,
            rating_explanation="e",
            member_ids=[entities[2].id],
        )
        await self._seed_communities([comm_high, comm_low])

        results_one = await community_context(
            [entities[0].id, entities[1].id, entities[2].id],
            graph_store=self.store,
            top_k=1,
        )
        assert len(results_one) == 1
        assert results_one[0].item.id == comm_high.id
        assert results_one[0].score == 2

        results_two = await community_context(
            [entities[0].id, entities[1].id, entities[2].id],
            graph_store=self.store,
            top_k=2,
        )
        assert len(results_two) == 2
        assert results_two[0].item.id == comm_high.id
        assert results_two[1].item.id == comm_low.id

    async def test_community_context_empty_no_query(self) -> None:
        """Empty entity_ids returns empty without a store query."""
        mock_store = AsyncMock()
        results = await community_context([], graph_store=mock_store)
        assert results == []
        mock_store.execute_read.assert_not_called()

        # Real store also returns empty for empty input.
        real_results = await community_context([], graph_store=self.store)
        assert real_results == []

    async def test_community_retriever_round_trip(self) -> None:
        """CommunityRetriever vector search round-trips via Neo4j."""
        entities = await self._seed_entities(["Alice"])
        comm_a = Community(
            id=uuid4(),
            title="Aspirin",
            summary="treats headaches effectively",
            rating=7.0,
            rating_explanation="e",
            member_ids=[entities[0].id],
        )
        comm_b = Community(
            id=uuid4(),
            title="Finance",
            summary="stock markets and trading",
            rating=6.0,
            rating_explanation="e",
            member_ids=[entities[0].id],
        )
        await self._seed_communities([comm_a, comm_b])

        retriever = CommunityRetriever(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        results = await retriever.retrieve("Aspirin headache", limit=5)

        assert len(results) >= 1
        assert all(isinstance(r.item, Community) for r in results)
        ids = {r.item.id for r in results}
        assert comm_a.id in ids or comm_b.id in ids

    async def test_hybrid_reranked_enrichment_fuses(self) -> None:
        """HYBRID_RERANKED with community_expand fuses a Community."""
        entities = await self._seed_entities(["Alice"])
        comm = Community(
            id=uuid4(),
            title="Community Alice",
            summary="Alice community summary",
            rating=8.0,
            rating_explanation="e",
            member_ids=[entities[0].id],
        )
        await self._seed_communities([comm])

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )

        async def _fake_rerank(
            query: str, results: list[SearchResult], **_: object
        ) -> list[SearchResult]:
            """Return results unchanged, preserving order."""
            return results

        with patch(
            "agrag.retrieval.search_engine.cross_encoder_rerank",
            new_callable=AsyncMock,
            side_effect=_fake_rerank,
        ):
            results = await engine.search("Alice", HYBRID_RERANKED)

        assert any(isinstance(r.item, Community) for r in results)

    async def test_post_bfs_seed_includes_neighbour(self) -> None:
        """BFS neighbours seed community_context entity_ids."""
        entities = await self._seed_entities(["Alice", "Bob"])
        await self._seed_relation(entities[0].id, entities[1].id, "KNOWS")
        comm = Community(
            id=uuid4(),
            title="Bob Community",
            summary="Bob neighbourhood",
            rating=5.0,
            rating_explanation="e",
            member_ids=[entities[1].id],
        )
        await self._seed_communities([comm])

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        recipe = Recipe(methods=["entity"], bfs=True, community_expand=True, limit=10)

        captured: dict[str, list[UUID]] = {}

        original_context = community_context

        async def _spy_context(
            entity_ids: list[UUID],
            *,
            graph_store: object = None,  # type: ignore[assignment]
            top_k: int = 3,
            filters: SearchFilters | None = None,
        ) -> list[SearchResult]:
            """Capture entity_ids and delegate to real community_context."""
            captured["ids"] = list(entity_ids)
            return await original_context(
                entity_ids,
                graph_store=graph_store,
                top_k=top_k,
                filters=filters,
            )

        with patch(
            "agrag.retrieval.search_engine.community_context",
            side_effect=_spy_context,
        ):
            await engine.search("Alice", recipe)

        assert "ids" in captured
        assert entities[1].id in captured["ids"]

    async def test_reserved_slice_not_cross_encoded_and_clamp(self) -> None:
        """Communities are not cross-encoded; reserved slice is clamped."""
        entities = await self._seed_entities(["Alice", "Bob", "Charlie", "Dave", "Eve"])
        # entities[0] ("Alice") is a member of every community: it is an
        # exact-vector match for the "Alice" query under _FixedEmbedder and
        # so always ranks first, regardless of the hash-based (per-process,
        # non-semantic) ranking of the other four entities. Community
        # overlap must not depend on which of those four the query's
        # top-`limit` slots happen to include.
        communities = [
            Community(
                id=uuid4(),
                title=f"Comm {i}",
                summary=f"Summary {i} Alice Bob",
                rating=5.0,
                rating_explanation="e",
                member_ids=[entities[0].id, entities[i + 1].id],
            )
            for i in range(3)
        ]
        await self._seed_communities(communities)

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )

        captured: dict[str, list[SearchResult]] = {}

        async def _capture_rerank(
            query: str, results: list[SearchResult], **_: object
        ) -> list[SearchResult]:
            """Record rerank input and return it unchanged."""
            captured["input"] = list(results)
            return results

        # Limit 3 with top_k 2: 2 slots reserved for communities.
        recipe = Recipe(
            methods=["entity"],
            reranker="cross_encoder",
            limit=3,
            community_expand=True,
            community_top_k=2,
        )
        with patch(
            "agrag.retrieval.search_engine.cross_encoder_rerank",
            new_callable=AsyncMock,
            side_effect=_capture_rerank,
        ):
            results = await engine.search("Alice", recipe)

        assert "input" in captured
        assert all(not isinstance(r.item, Community) for r in captured["input"])
        assert sum(1 for r in results if isinstance(r.item, Community)) == 2
        assert len(results) == 3

        # Clamp: limit 1 with top_k 3 must not error and returns 1 Community.
        captured.clear()
        clamp_recipe = Recipe(
            methods=["entity"],
            reranker="cross_encoder",
            limit=1,
            community_expand=True,
            community_top_k=3,
        )
        with patch(
            "agrag.retrieval.search_engine.cross_encoder_rerank",
            new_callable=AsyncMock,
            side_effect=_capture_rerank,
        ):
            clamp_results = await engine.search("Alice", clamp_recipe)

        assert len(clamp_results) == 1
        assert any(isinstance(r.item, Community) for r in clamp_results)

    async def test_zero_overlap_no_reserved_error(self) -> None:
        """Zero community overlap does not raise and reserves nothing."""
        await self._seed_entities(["Alice"])
        comm = Community(
            id=uuid4(),
            title="Isolated",
            summary="No overlap community",
            rating=5.0,
            rating_explanation="e",
            member_ids=[uuid4()],
        )
        await self._seed_communities([comm])

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        recipe = Recipe(
            methods=["entity"],
            reranker="cross_encoder",
            limit=5,
            community_expand=True,
            community_top_k=2,
        )

        async def _fake_rerank(
            query: str, results: list[SearchResult], **_: object
        ) -> list[SearchResult]:
            """Return results unchanged."""
            return results

        with patch(
            "agrag.retrieval.search_engine.cross_encoder_rerank",
            new_callable=AsyncMock,
            side_effect=_fake_rerank,
        ):
            results = await engine.search("Alice", recipe)

        assert isinstance(results, list)
        assert len(results) <= 5
        assert all(not isinstance(r.item, Community) for r in results)

    async def test_filter_scoping(self) -> None:
        """THEMATIC forwards document_ids and properties, not labels.

        Community nodes carry no document/tenant scope of their own, so
        document_ids is forwarded deliberately: it makes a document- or
        property-scoped search fail closed (no community results) rather
        than return a report drawn from outside that scope. Labels are
        never forwarded, since they check node labels and a Community
        node never carries an entity label.
        """
        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        filters = SearchFilters(
            labels=["Person"],
            document_ids=[str(uuid4())],
            properties={"rating": 5.0},
        )

        captured: dict[str, SearchFilters | None] = {}

        async def _capture_vector_search(*_: object, **kwargs: object) -> list:
            """Capture filters passed to community vector_search."""
            filt = kwargs.get("filters")
            if isinstance(filt, SearchFilters) or filt is None:
                captured["filters"] = filt
            return []

        with patch(
            "agrag.retrieval.retrievers.community.vector_search",
            new_callable=AsyncMock,
            side_effect=_capture_vector_search,
        ):
            await engine.search("theme query", THEMATIC, filters=filters)

        assert "filters" in captured
        filt = captured["filters"]
        assert filt is not None
        assert filt.properties == {"rating": 5.0}
        assert filt.labels == []
        assert filt.document_ids == filters.document_ids

    async def test_thematic_bounded(self) -> None:
        """THEMATIC respects its limit."""
        entities = await self._seed_entities(["Alice"])
        communities = [
            Community(
                id=uuid4(),
                title=f"T{i}",
                summary=f"S{i} thematic content",
                rating=5.0,
                rating_explanation="e",
                member_ids=[entities[0].id],
            )
            for i in range(6)
        ]
        await self._seed_communities(communities)

        engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
        )
        # THEMATIC has limit 5. These bounds are only meaningful with a hit
        # to bound, so a cold index must not pass as an empty result set.
        results = await engine.search("thematic", THEMATIC)
        assert results
        assert len(results) <= 5
        assert all(isinstance(r.item, Community) for r in results)

        # Custom bounded recipe.
        small = Recipe(methods=["community"], limit=2)
        small_results = await engine.search("thematic", small)
        assert small_results
        assert len(small_results) <= 2

    async def test_ledger_G_prefix(self) -> None:
        """Ledger assigns G prefix to Community citations."""
        comm = Community(
            id=uuid4(),
            title="G Community",
            summary="Summary for ledger test",
            rating=9.0,
            rating_explanation="highly relevant",
            member_ids=[uuid4()],
        )
        result = SearchResult(item=comm, score=1.0, method="community")
        ledger = Ledger()
        key = ledger.cite(result)

        assert key.startswith("G")
        resolved = ledger.resolve(key)
        assert resolved is not None
        assert resolved.item.id == comm.id
        rendered = ledger.render(result)
        assert key in rendered
        assert "Community" in rendered

        # Second community gets G2.
        comm2 = Community(
            id=uuid4(),
            title="G2",
            summary="Second",
            rating=5.0,
            rating_explanation="e",
        )
        key2 = ledger.cite(SearchResult(item=comm2, score=0.9, method="community"))
        assert key2 == "G2"
        assert key2.startswith("G")
