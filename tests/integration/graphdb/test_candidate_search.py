"""Candidate search checks committed review groups and their lexical ranking."""

import importlib.util
from collections.abc import AsyncIterator, Sequence
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.candidate import (
    CANDIDATE_LABEL,
    EVIDENCED_BY,
    CandidateRecord,
)
from agrag.common.data_models.graph_record import NodeRecord
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.retrieval.search_engine import SearchEngine


neo4j_missing = importlib.util.find_spec("neo4j") is None
pytestmark = [
    pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed"),
    pytest.mark.xdist_group(name="candidate_state"),
]


class _TestEmbedder(Embedder):
    """Provide a valid embedder for SearchEngine construction."""

    model = "candidate-search-test"

    async def dimensions(self) -> int:
        return 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0, 1.0] for _ in texts]


@pytest_asyncio.fixture
async def store() -> AsyncIterator[GraphStore]:
    """Open the configured Neo4j store for the candidate search scenario."""
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    await graph_store.setup_constraints()
    try:
        yield graph_store
    finally:
        await graph_store.close()


class TestSearchCandidates:
    """SearchEngine returns only matching, committed candidate groups."""

    async def test_searches_matching_review_groups_in_rank_order(
        self, store: GraphStore
    ) -> None:
        """Punctuation, review state, aggregation and ranking affect results."""
        token = uuid4().hex
        chunk_ids = [uuid4() for _ in range(7)]
        candidate_ids = [uuid4() for _ in range(7)]
        records = [
            CandidateRecord(
                kind="entity",
                label="Organization",
                text=f"Acme, {token}",
                confidence=0.7,
                reason="entity_band",
                chunk_id=chunk_ids[0],
                count=2,
            ),
            CandidateRecord(
                kind="entity",
                label="Organization",
                text=f"Acme {token}",
                confidence=0.8,
                reason="entity_band",
                chunk_id=chunk_ids[1],
                count=3,
            ),
            CandidateRecord(
                kind="relation",
                label="WORKS_FOR",
                source_text="Ada",
                target_text=f"Acme {token}",
                confidence=0.6,
                reason="off_pattern",
                chunk_id=chunk_ids[2],
                state="approved",
                count=1,
            ),
            CandidateRecord(
                kind="entity",
                label="Organization",
                text=f"Acme {token}",
                confidence=0.9,
                reason="entity_band",
                chunk_id=chunk_ids[3],
                state="rejected",
                count=100,
            ),
            CandidateRecord(
                id=candidate_ids[4],
                kind="entity",
                label="Organization",
                text=f"hidden-candidate {token}",
                confidence=0.5,
                reason="entity_band",
                chunk_id=chunk_ids[4],
            ),
            CandidateRecord(
                id=candidate_ids[5],
                kind="entity",
                label="Organization",
                text=f"hidden-evidence {token}",
                confidence=0.5,
                reason="entity_band",
                chunk_id=chunk_ids[5],
            ),
            CandidateRecord(
                id=candidate_ids[6],
                kind="entity",
                label="Organization",
                text=f"hidden-chunk {token}",
                confidence=0.5,
                reason="entity_band",
                chunk_id=chunk_ids[6],
            ),
        ]
        try:
            await store.upsert_nodes(
                "Chunk",
                [
                    NodeRecord(id=chunk_id, labels=["Chunk"], properties={})
                    for chunk_id in chunk_ids
                ],
            )
            for record in records:
                assert (await store.upsert_candidates([record])).written == 1

            await store.execute_write(
                f"MATCH (candidate:{CANDIDATE_LABEL}) "
                "WHERE candidate.id = $id "
                "SET candidate._pending_job_id = $job_id",
                {"id": str(candidate_ids[4]), "job_id": str(uuid4())},
            )
            await store.execute_write(
                f"MATCH (candidate:{CANDIDATE_LABEL})-[evidence:{EVIDENCED_BY}]->() "
                "WHERE candidate.id = $id "
                "SET evidence._pending_job_id = $job_id",
                {"id": str(candidate_ids[5]), "job_id": str(uuid4())},
            )
            await store.execute_write(
                f"MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk) "
                "WHERE chunk.id = $id "
                "SET chunk._pending_job_id = $job_id",
                {"id": str(chunk_ids[6]), "job_id": str(uuid4())},
            )

            engine = SearchEngine(graph_store=store, embedder=_TestEmbedder())
            found = await engine.search_candidates(f"ACME? {token}", limit=10)

            assert [(record.kind, record.state, record.count) for record in found] == [
                ("entity", "pending", 5),
                ("relation", "approved", 1),
            ]
            assert found[0].text in {f"Acme, {token}", f"Acme {token}"}

            relations = await engine.search_candidates(
                f"ACME? {token}", kind="relation"
            )
            assert [record.kind for record in relations] == ["relation"]
            limited = await engine.search_candidates(f"ACME? {token}", limit=1)
            assert limited == found[:1]
            assert await engine.search_candidates("!? aa") == []

        finally:
            await store.execute_write(
                f"MATCH (candidate:{CANDIDATE_LABEL}) "
                "WHERE candidate.id IN $ids DETACH DELETE candidate",
                {"ids": [str(record.id) for record in records]},
            )
            await store.execute_write(
                f"MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk) "
                "WHERE chunk.id IN $ids DETACH DELETE chunk",
                {"ids": [str(chunk_id) for chunk_id in chunk_ids]},
            )
