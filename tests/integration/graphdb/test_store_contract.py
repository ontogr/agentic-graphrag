"""Contract tests that every graph-store backend must pass.

The backend comes from ``AGRAG_TEST_BACKENDS`` (see ``tests/integration/_backend.py``).
Each test uses labels with a unique suffix, so tests can share one database.
"""

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
)
from agrag.common.data_models.index_record import INDEX_STATE_ONLINE
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.errors import EmbeddingDimensionMismatchError
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreConstraintViolationError
from tests.integration._backend import (
    await_indexes,
    build_test_store,
    selected_backend,
)


pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(loop_scope="module")
async def store() -> AsyncIterator[GraphStore]:
    """Provide a connected store for the selected backend."""
    graph_store = build_test_store()
    await graph_store.connect()
    try:
        yield graph_store
    finally:
        await graph_store.close()


# Labels written by the running test, deleted with their nodes when it ends.
_created_labels: list[str] = []


def _label(prefix: str) -> str:
    """Return a label no other test uses and record it for cleanup."""
    label = f"{prefix}{uuid4().hex[:8]}"
    _created_labels.append(label)
    return label


@pytest_asyncio.fixture(autouse=True, loop_scope="module")
async def remove_test_nodes(store: GraphStore) -> AsyncIterator[None]:
    """Delete the nodes and relationships each test wrote under its labels."""
    yield
    while _created_labels:
        label = _created_labels.pop()
        await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")


def _node(label: str, **properties: object) -> NodeRecord:
    """Build a node record with one label."""
    return NodeRecord(id=uuid4(), labels=[label], properties=dict(properties))


class TestStoreContract:
    """Behavior every backend provides through the ``GraphStore`` interface."""

    async def test_reads_back_what_it_wrote(self, store: GraphStore) -> None:
        """A written node is readable with the properties it was given."""
        label = _label("Thing")
        node = _node(label, name="Ada", rank=3, tags=["a", "b"])

        result = await store.upsert_nodes(label, [node])
        rows = await store.execute_read(
            f"MATCH (n:{label} {{id: $id}}) RETURN n.name AS name, n.rank AS rank, "
            "n.tags AS tags, labels(n) AS labels",
            {"id": str(node.id)},
        )

        assert result.written == 1
        assert result.failures == []
        assert rows[0]["name"] == "Ada"
        assert rows[0]["rank"] == 3
        assert rows[0]["tags"] == ["a", "b"]
        assert label in rows[0]["labels"]
        assert NODE_IDENTITY_LABEL in rows[0]["labels"]

    async def test_upserting_the_same_id_twice_keeps_one_node(
        self, store: GraphStore
    ) -> None:
        """Repeated and concurrent upserts of one id leave a single node."""
        label = _label("Same")
        node = _node(label, name="first")
        changed = node.model_copy(update={"properties": {"name": "second"}})

        await asyncio.gather(
            *[store.upsert_nodes(label, [node]) for _ in range(8)],
            store.upsert_nodes(label, [changed]),
        )
        rows = await store.execute_read(
            f"MATCH (n:{label}) RETURN count(n) AS count, collect(n.name) AS names"
        )

        assert rows[0]["count"] == 1
        assert rows[0]["names"][0] in {"first", "second"}

    async def test_upserts_relations_and_reports_missing_endpoints(
        self, store: GraphStore
    ) -> None:
        """A relation joins existing nodes and a missing endpoint is a failure."""
        label = _label("Person")
        rel_type = f"KNOWS_{uuid4().hex[:8].upper()}"
        left, right = _node(label, name="L"), _node(label, name="R")
        await store.upsert_nodes(label, [left, right])
        good = RelationRecord(
            id=uuid4(),
            type=rel_type,
            start_id=left.id,
            end_id=right.id,
            properties={"since": 2020},
        )
        dangling = RelationRecord(
            id=uuid4(),
            type=rel_type,
            start_id=left.id,
            end_id=uuid4(),
            properties={},
        )

        result = await store.upsert_relations([good, dangling])
        rows = await store.execute_read(
            f"MATCH (:{label})-[r:{rel_type}]->(:{label}) RETURN r.since AS since"
        )

        assert result.written == 1
        assert [failure.id for failure in result.failures] == [str(dangling.id)]
        assert result.failures[0].error_type == "MissingEndpoint"
        assert [row["since"] for row in rows] == [2020]

    async def test_isolates_a_record_that_cannot_be_stored(
        self, store: GraphStore
    ) -> None:
        """One unstorable record is reported and the others still write."""
        label = _label("Isolate")
        good = _node(label, name="fine")
        bad = _node(label, name="bad", nested={"not": "allowed"})

        result = await store.upsert_nodes(label, [good, bad])
        rows = await store.execute_read(
            f"MATCH (n:{label}) RETURN n.name AS name ORDER BY name"
        )

        assert result.written == 1
        assert [failure.id for failure in result.failures] == [str(bad.id)]
        assert [row["name"] for row in rows] == ["fine"]

    async def test_defers_a_write_over_a_row_another_job_owns(
        self, store: GraphStore
    ) -> None:
        """A job write to a row the job did not create is held, not applied."""
        label = _label("Owned")
        node = _node(label, name="original")
        await store.upsert_nodes(
            label, [node], pending_job_id=uuid4(), deferred=DeferredWrites()
        )
        deferred = DeferredWrites()

        changed = node.model_copy(update={"properties": {"name": "changed"}})
        await store.upsert_nodes(
            label, [changed], pending_job_id=uuid4(), deferred=deferred
        )
        rows = await store.execute_read(f"MATCH (n:{label}) RETURN n.name AS name")

        assert rows[0]["name"] == "original"
        assert len(deferred.entries) == 1

    async def test_rejects_a_duplicate_id_after_setup(self, store: GraphStore) -> None:
        """The identity constraint stops a second node with the same id."""
        label = _label("Unique")
        node = _node(label, name="once")
        await store.upsert_nodes(label, [node])
        await store.setup_constraints()

        with pytest.raises(GraphStoreConstraintViolationError):
            await store.execute_write(
                f"CREATE (:{NODE_IDENTITY_LABEL} {{id: $id}})", {"id": str(node.id)}
            )

    async def test_vector_search_returns_closest_first_on_one_scale(
        self, store: GraphStore
    ) -> None:
        """Cosine scores run from 1.0 for identical to 0.5 for orthogonal."""
        label = _label("Vec")
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=3,
            distance=Distance.COSINE,
        )
        vectors = {
            "same": [1.0, 0.0, 0.0],
            "near": [0.7, 0.7, 0.0],
            "orthogonal": [0.0, 1.0, 0.0],
        }
        nodes = {
            name: _node(label, name=name, embedding=vector)
            for name, vector in vectors.items()
        }
        await store.upsert_nodes(label, list(nodes.values()))

        hits = await store.vector_search(
            label=label,
            vector_property="embedding",
            query_vector=[1.0, 0.0, 0.0],
            limit=3,
        )

        by_name = {hit.payload["name"]: hit for hit in hits}
        assert [hit.payload["name"] for hit in hits] == ["same", "near", "orthogonal"]
        assert by_name["same"].score == pytest.approx(1.0, abs=0.02)
        assert by_name["near"].score == pytest.approx(0.8536, abs=0.02)
        assert by_name["orthogonal"].score == pytest.approx(0.5, abs=0.02)
        assert "embedding" not in by_name["same"].payload

    async def test_vector_search_applies_a_filter_to_the_candidates(
        self, store: GraphStore
    ) -> None:
        """A filter that rejects the nearest nodes still returns the others."""
        label = _label("Filt")
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=2,
            distance=Distance.COSINE,
        )
        nodes = [
            _node(label, kind="a" if index < 6 else "b", embedding=[1.0, index / 10])
            for index in range(8)
        ]
        await store.upsert_nodes(label, nodes)

        hits = await store.vector_search(
            label=label,
            vector_property="embedding",
            query_vector=[1.0, 0.0],
            limit=2,
            filters={"kind": "b"},
        )

        assert len(hits) == 2
        assert {hit.payload["kind"] for hit in hits} == {"b"}

    async def test_a_vector_index_rejects_a_different_dimension(
        self, store: GraphStore
    ) -> None:
        """Asking for another dimension than the index has raises."""
        label = _label("Dim")
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=3,
            distance=Distance.COSINE,
        )

        with pytest.raises(EmbeddingDimensionMismatchError):
            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=5,
                distance=Distance.COSINE,
            )

    async def test_a_wrong_length_embedding_is_reported_not_stored(
        self, store: GraphStore
    ) -> None:
        """An embedding that does not fit the index is a failure, not a silent gap."""
        label = _label("Len")
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=3,
            distance=Distance.COSINE,
        )
        good = _node(label, name="fits", embedding=[1.0, 0.0, 0.0])
        bad = _node(label, name="short", embedding=[1.0, 0.0])

        result = await store.upsert_nodes(label, [good, bad])

        if selected_backend() == "falkordb":
            assert result.written == 1
            assert [failure.id for failure in result.failures] == [str(bad.id)]
        hits = await store.vector_search(
            label=label,
            vector_property="embedding",
            query_vector=[1.0, 0.0, 0.0],
            limit=5,
        )
        assert [hit.payload["name"] for hit in hits] == ["fits"]

    async def test_lists_online_indexes(self, store: GraphStore) -> None:
        """Created vector and full-text indexes are listed as online."""
        label = _label("Idx")
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=3,
            distance=Distance.COSINE,
        )
        await store.ensure_fulltext_index(label=label, properties=["title", "body"])
        await await_indexes(store)

        indexes = [
            index for index in await store.list_indexes() if index.labels == [label]
        ]

        by_type = {index.type: index for index in indexes}
        assert by_type["VECTOR"].properties == ["embedding"]
        assert by_type["VECTOR"].dimensions == 3
        assert sorted(by_type["FULLTEXT"].properties) == ["body", "title"]
        assert all(index.state == INDEX_STATE_ONLINE for index in indexes)

    async def test_full_text_search_finds_matching_words(
        self, store: GraphStore
    ) -> None:
        """A full-text call returns nodes whose text has a query word."""
        label = _label("Text")
        await store.ensure_fulltext_index(label=label, properties=["text"])
        match = _node(label, text="the quick brown fox")
        other = _node(label, text="slow green turtle")
        await store.upsert_nodes(label, [match, other])
        await await_indexes(store)
        call = await store.fulltext_search_call(label=label, properties=["text"])

        rows = await store.execute_read(
            f"{call.text} RETURN node.id AS id, score ORDER BY score DESC",
            {**call.params, "fulltext_terms": "fox", "k": 5},
        )

        assert [row["id"] for row in rows] == [str(match.id)]

    async def test_full_text_search_finds_text_written_before_the_index(
        self, store: GraphStore
    ) -> None:
        """Text written before a full-text index exists is still searchable."""
        label = _label("Backfill")
        # A property no other test indexes, so the store has no search copy
        # for it from an earlier test when this one writes.
        prop = f"body_{uuid4().hex[:8]}"
        match = _node(label, **{prop: "the quick brown fox"})
        other = _node(label, **{prop: "slow green turtle"})
        await store.upsert_nodes(label, [match, other])

        await store.ensure_fulltext_index(label=label, properties=[prop])
        await await_indexes(store)
        call = await store.fulltext_search_call(label=label, properties=[prop])

        rows = await store.execute_read(
            f"{call.text} RETURN node.id AS id",
            {**call.params, "fulltext_terms": "fox", "k": 5},
        )

        assert [row["id"] for row in rows] == [str(match.id)]

    @pytest.mark.skipif(
        selected_backend() != "falkordb",
        reason="only FalkorDB restricts a full-text search to some properties",
    )
    async def test_full_text_search_is_limited_to_the_requested_properties(
        self, store: GraphStore
    ) -> None:
        """A term found only in another indexed property does not match."""
        label = _label("Scope")
        await store.ensure_fulltext_index(label=label, properties=["title", "body"])
        in_title = _node(label, title="zebra", body="apple")
        in_body = _node(label, title="apple", body="zebra")
        await store.upsert_nodes(label, [in_title, in_body])
        await await_indexes(store)
        call = await store.fulltext_search_call(label=label, properties=["title"])

        rows = await store.execute_read(
            f"{call.text} RETURN node.id AS id",
            {**call.params, "fulltext_terms": "zebra", "k": 5},
        )

        assert [row["id"] for row in rows] == [str(in_title.id)]

    @pytest.mark.skipif(
        selected_backend() != "falkordb",
        reason="only FalkorDB checks embedding lengths on write",
    )
    async def test_an_attached_store_rejects_a_wrong_length_embedding_like_the_creator(
        self, store: GraphStore
    ) -> None:
        """A store that finds an index it did not create refuses the same record."""
        label = _label("Attach")
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=3,
            distance=Distance.COSINE,
        )
        bad = _node(label, name="short", embedding=[1.0, 0.0])
        attached = build_test_store()
        await attached.connect()
        try:
            created_outcome = await store.upsert_nodes(label, [bad])
            attached_outcome = await attached.upsert_nodes(label, [bad])
        finally:
            await attached.close()

        assert created_outcome.written == 0
        assert [failure.error_type for failure in created_outcome.failures] == [
            "EmbeddingDimensionMismatchError"
        ]
        assert attached_outcome.failures == created_outcome.failures

    @pytest.mark.skipif(
        selected_backend() == "neo4j",
        reason="Neo4j keeps an existing index without comparing its similarity",
    )
    async def test_a_vector_index_rejects_a_different_similarity(
        self, store: GraphStore
    ) -> None:
        """Asking for another similarity function than the index has raises."""
        label = _label("Sim")
        await store.ensure_vector_index(
            label=label,
            vector_property="embedding",
            dimensions=3,
            distance=Distance.EUCLID,
        )

        with pytest.raises(ValueError, match="euclidean"):
            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=3,
                distance=Distance.COSINE,
            )

    async def test_transaction_commits_every_statement(self, store: GraphStore) -> None:
        """Statements in one callback are all applied and results come back."""
        label = _label("Tx")
        first, second = _node(label, name="one"), _node(label, name="two")

        async def work(transaction: GraphStoreTransaction) -> int:
            await transaction.upsert_nodes(label, [first])
            await transaction.upsert_nodes(label, [second])
            rows = await transaction.execute_read(
                f"MATCH (n:{label}) RETURN count(n) AS count"
            )
            return rows[0]["count"]

        assert await store.run_in_transaction(work) == 2

    async def test_a_failing_transaction_rolls_back_on_neo4j_only(
        self, store: GraphStore
    ) -> None:
        """Neo4j undoes a failed callback; other backends keep earlier writes."""
        label = _label("Rollback")
        node = _node(label, name="kept?")

        async def work(transaction: GraphStoreTransaction) -> None:
            await transaction.upsert_nodes(label, [node])
            raise RuntimeError("stop")

        with pytest.raises(RuntimeError):
            await store.run_in_transaction(work)
        rows = await store.execute_read(f"MATCH (n:{label}) RETURN count(n) AS count")

        assert rows[0]["count"] == (0 if selected_backend() == "neo4j" else 1)
