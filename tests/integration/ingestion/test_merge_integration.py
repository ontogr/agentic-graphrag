"""Integration tests for merge mechanics against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The ``skipif``
only guards the missing extra; with the extra installed the tests expect a
reachable Neo4j at the default ``NEO4J_URI``.
"""

import asyncio
import importlib.util
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk as ChunkModel
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import set_embedding_query, validate_identifier
from agrag.cypher.schema import merge_key_constraint_query
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.errors import GraphStoreAliasConflictError
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph, _apply_merge_with_conflict_retry
from agrag.ingestion.merge import (
    PropertyRules,
    PropertyStrategy,
    apply_merge,
    compute_merge,
    mentioned_in_id,
)
from agrag.loaders.corpus.types import ErrorPolicy


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestApplyMergeConstraintIntegration:
    """Regression coverage for the per-label merge_key uniqueness constraint."""

    async def test_survivor_adopting_absorbed_name_commits(self) -> None:
        """A survivor whose resolved name matches a tombstone's name commits.

        Canonical selection picks entity B as survivor while KEEP_FIRST
        resolves the name from entity A, so the survivor's resolved
        merge_key equals A's still-live merge_key at the moment the merge
        runs. Without clearing A's merge_key before the survivor is written,
        Neo4j rejects the whole transaction with a constraint violation
        instead of committing the merge.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        try:
            # entity_a is listed first (so KEEP_FIRST resolves the survivor's
            # name from it) but is created later, so _select_canonical picks
            # entity_b as the survivor on the created_at tiebreak.
            entity_a = Entity(
                id=uuid4(),
                label=label,
                name="Ada Lovelace",
                created_at=datetime.now(UTC),
            )
            entity_b = Entity(
                id=uuid4(),
                label=label,
                name="A. Lovelace",
                created_at=datetime.now(UTC) - timedelta(minutes=5),
            )
            await store.upsert_nodes(
                label, [entity_a.to_node_record(), entity_b.to_node_record()]
            )
            # A direct, label-scoped constraint instead of setup_constraints():
            # that sweeps every label the whole database has ever seen, so on a
            # long-lived shared instance it can fail on unrelated leftover state.
            await store.execute_write(merge_key_constraint_query(label))

            plan, _ = await compute_merge(
                existing_entities=[entity_a, entity_b],
                mentions=[],
                schema=schema,
                rules=PropertyRules(default=PropertyStrategy.KEEP_FIRST),
            )
            assert plan.survivor.id == entity_b.id
            assert plan.survivor.name == entity_a.name
            assert plan.tombstone_ids == [entity_a.id]

            await apply_merge(plan, graph_store=store, schema=schema)

            survivor_rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) RETURN n.merge_key AS merge_key",
                {"id": str(entity_b.id)},
            )
            assert survivor_rows[0]["merge_key"] == entity_a.merge_key

            tombstone_rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) "
                f"RETURN n.merge_key AS merge_key, n.merged_into AS merged_into",
                {"id": str(entity_a.id)},
            )
            assert tombstone_rows[0]["merge_key"] is None
            assert tombstone_rows[0]["merged_into"] == str(entity_b.id)
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestApplyMergeAliasConflictIntegration:
    """Regression coverage for a merge-key alias claimed by another entity."""

    async def test_bob_racing_robert_recovers_into_one_entity(self) -> None:
        """Canonical "Bob" races an entity resolving "Bob" as an alias of "Robert".

        Simulates the race deterministically, in sequence: one writer
        commits a canonical entity named "Bob" first; a second writer then
        separately resolves mentions "Robert" and "Bob" as the same entity
        and tries to accept "Bob" as an alias. Neither writer's own node
        merge_key collides (their own names differ), so nothing at the
        database level rejects the second write; without recovery it would
        leave two live entities that both believe they own the name "Bob".
        """
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        try:
            await store.execute_write(merge_key_constraint_query(label))

            bob_mention = ExtractedEntity(
                chunk_id=uuid4(), label=label, text="Bob", char_start=0, char_end=3
            )
            plan_a, _ = await compute_merge(
                existing_entities=[], mentions=[bob_mention], schema=schema
            )
            await apply_merge(plan_a, graph_store=store, schema=schema)

            robert_mention = ExtractedEntity(
                chunk_id=uuid4(), label=label, text="Robert", char_start=0, char_end=6
            )
            plan_b, _ = await compute_merge(
                existing_entities=[],
                mentions=[robert_mention, bob_mention],
                schema=schema,
            )
            assert plan_b.survivor.id != plan_a.survivor.id

            with pytest.raises(GraphStoreAliasConflictError) as exc_info:
                await apply_merge(plan_b, graph_store=store, schema=schema)
            assert exc_info.value.conflicts == {f"{label}:bob": str(plan_a.survivor.id)}

            # The rejected transaction must have committed nothing: plan_b's
            # own node never becomes a second live entity for "Bob".
            rejected_rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) RETURN n",
                {"id": str(plan_b.survivor.id)},
            )
            assert rejected_rows == []

            recovered_plan, _ = await _apply_merge_with_conflict_retry(
                plan_b,
                graph_store=store,
                schema=schema,
                existing_entities=[],
                mentions=[robert_mention, bob_mention],
                is_new_entity=True,
            )

            assert recovered_plan.survivor.id == plan_a.survivor.id
            count_rows = await store.execute_read(
                f"MATCH (n:{label}) RETURN count(n) AS c", {}
            )
            assert count_rows[0]["c"] == 1

            robert_lookup = await store.execute_read(
                f"MATCH (a:_AgragMergeAlias {{merge_key: $mk}}) "
                f"MATCH (n:{label} {{id: a.entity_id}}) RETURN n.id AS id",
                {"mk": f"{label}:robert"},
            )
            assert robert_lookup[0]["id"] == str(plan_a.survivor.id)
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) "
                "WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            await store.close()


class _StubEmbedder(Embedder):
    """Embedder that returns a fixed vector, for tests that never search."""

    model = "stub"

    async def dimensions(self) -> int:
        """Return a fixed dimension count."""
        return 3

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for each input text."""
        return [[1.0, 2.0, 3.0] for _ in texts]


async def _vector_search_with_retry(
    store: Neo4jGraphStore,
    *,
    label: str,
    query_vector: list[float],
    limit: int,
) -> list:
    """Retry the vector search while a newly created index warms up."""
    last: list = []
    for _ in range(10):
        last = await store.vector_search(
            label=label,
            vector_property="embedding",
            query_vector=query_vector,
            limit=limit,
        )
        if last:
            return last
        await asyncio.sleep(1)
    return last


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestMentionedInTransferIntegration:
    """Regression coverage for a MENTIONED_IN edge transferred by a merge."""

    async def test_reingesting_after_merge_does_not_duplicate_mentioned_in(
        self,
    ) -> None:
        """Re-ingesting a chunk after its mentioned entity was merged away.

        ``transfer_relationships_query`` preserves a transferred edge's
        tombstone-derived id rather than recomputing it for the survivor.
        Without an endpoint lookup before writing, ``Graph.add``'s
        MENTIONED_IN upsert would recompute a fresh id for the same (chunk,
        entity) pair and create a second, parallel edge instead of
        converging onto the one the merge already transferred.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        text = "Ada Lovelace wrote the first algorithm."
        chunk_ids: list[UUID] = []

        class NoEntitiesExtractor(Extractor):
            """Chunks the text without extracting anything, to learn its id."""

            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                chunk_ids.append(chunk.id)
                return ExtractionResult(
                    entities=[], relations=[], extractor_name="fake"
                )

        class AdaExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                chunk_ids.append(chunk.id)
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label=label,
                            text="Ada Lovelace",
                            char_start=0,
                            char_end=12,
                        )
                    ],
                    relations=[],
                    extractor_name="fake",
                )  # type: ignore[arg-type]

        # Graph() directly, not Graph.open(): open() runs setup_constraints(),
        # which sweeps every label this whole shared Neo4j instance has ever
        # seen, not just this test's own randomly suffixed label. Nothing
        # this test exercises depends on that constraint existing.
        graph = Graph(
            schema=schema,
            graph_store=store,
            embedder=_StubEmbedder(),
            extractor=NoEntitiesExtractor(),
        )
        try:
            # A priming ingest that writes only the Chunk node, so its id is
            # the real, deterministic id chunking gives this text -- without
            # involving entity resolution or the merge-key alias table yet.
            await graph.add(text=text)
            chunk_id = chunk_ids[0]

            entity_a = Entity(id=uuid4(), label=label, name="Ada Lovelace")
            # Earlier created_at wins canonical selection, so this becomes
            # the merge survivor and entity_a is tombstoned into it.
            entity_b = Entity(
                id=uuid4(),
                label=label,
                name="A. Lovelace",
                created_at=entity_a.created_at - timedelta(minutes=5),
            )
            await store.upsert_nodes(
                label, [entity_a.to_node_record(), entity_b.to_node_record()]
            )
            await store.execute_write(merge_key_constraint_query(label))

            # The edge an earlier, real ingest of this chunk would have
            # written: Chunk -[:MENTIONED_IN]-> entity_a.
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=mentioned_in_id(chunk_id, entity_a.id),
                        type="MENTIONED_IN",
                        start_id=chunk_id,
                        end_id=entity_a.id,
                        properties={"created_at": datetime.now(UTC).isoformat()},
                    )
                ]
            )

            plan, _ = await compute_merge(
                existing_entities=[entity_a, entity_b], mentions=[], schema=schema
            )
            assert plan.survivor.id == entity_b.id
            assert plan.tombstone_ids == [entity_a.id]
            await apply_merge(plan, graph_store=store, schema=schema)

            mentioned_before = await store.execute_read(
                "MATCH (:Chunk)-[r:MENTIONED_IN]->(n {id: $id}) RETURN r.id AS id",
                {"id": str(entity_b.id)},
            )
            assert len(mentioned_before) == 1

            # Re-ingest the same chunk: same text hashes to the same chunk
            # id, and the mention resolves straight to the survivor, since
            # neither name had a merge-key alias before this merge created
            # one -- no tombstone chain to follow.
            graph._extractor = AdaExtractor()
            await graph.add(text=text)
            assert chunk_ids[1] == chunk_id

            mentioned_after = await store.execute_read(
                "MATCH (:Chunk)-[r:MENTIONED_IN]->(n {id: $id}) RETURN r.id AS id",
                {"id": str(entity_b.id)},
            )
            assert len(mentioned_after) == 1
            assert mentioned_after[0]["id"] == mentioned_before[0]["id"]
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) "
                "WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            for chunk_id in set(chunk_ids):
                await store.execute_write(
                    "MATCH (c:Chunk {id: $id}) DETACH DELETE c", {"id": str(chunk_id)}
                )
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestReingestAbsorbedNameAliasIntegration:
    """Regression coverage for reingesting a name an earlier merge absorbed."""

    async def test_reingesting_absorbed_name_does_not_raise_false_conflict(
        self,
    ) -> None:
        """A mention of a long-absorbed name resolves instead of false-conflicting.

        Merge 1 creates a canonical entity "Bob" with a merge-key alias
        pointing at its own id. Merge 2 absorbs "Bob" into a separate
        survivor "Robert"; ``upsert_merge_alias_query`` never rewrites an
        existing alias, so "bob"'s alias still points at the now-tombstoned
        "Bob" id. Reingesting a "Bob" mention afterward resolves, through
        that stale alias and its ``merged_into`` chain, straight to
        "Robert" -- and must accept "bob" as one of this merge's own
        accepted keys rather than reading the stale alias owner as a
        foreign conflict.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        try:
            await store.execute_write(merge_key_constraint_query(label))

            bob_mention = ExtractedEntity(
                chunk_id=uuid4(), label=label, text="Bob", char_start=0, char_end=3
            )
            plan_bob, _ = await compute_merge(
                existing_entities=[], mentions=[bob_mention], schema=schema
            )
            await apply_merge(plan_bob, graph_store=store, schema=schema)

            entity_robert = Entity(
                id=uuid4(),
                label=label,
                name="Robert",
                created_at=plan_bob.survivor.created_at - timedelta(minutes=5),
            )
            await store.upsert_nodes(label, [entity_robert.to_node_record()])

            absorb_plan, _ = await compute_merge(
                existing_entities=[entity_robert, plan_bob.survivor],
                mentions=[],
                schema=schema,
            )
            assert absorb_plan.survivor.id == entity_robert.id
            assert absorb_plan.tombstone_ids == [plan_bob.survivor.id]
            await apply_merge(absorb_plan, graph_store=store, schema=schema)

            class BobAgainExtractor(Extractor):
                async def extract(
                    self, chunk: ChunkModel, schema: GraphSchema
                ) -> ExtractionResult:
                    return ExtractionResult(
                        entities=[
                            ExtractedEntity(
                                chunk_id=chunk.id,
                                label=label,
                                text="Bob",
                                char_start=0,
                                char_end=3,
                            )
                        ],
                        relations=[],
                        extractor_name="fake",
                    )  # type: ignore[arg-type]

            graph = Graph(
                schema=schema,
                graph_store=store,
                embedder=_StubEmbedder(),
                extractor=BobAgainExtractor(),
            )
            result = await graph.add(
                text="Bob mentioned again.", error_policy=ErrorPolicy.RAISE
            )
            assert not result.merge.failures
            # Resolved onto the existing survivor, not a fresh duplicate
            # "Bob" node that happened to reconcile afterward.
            assert result.merge.nodes_created == 0

            survivor_rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) "
                f"RETURN n.merge_count AS merge_count, "
                f"n.merged_into AS merged_into",
                {"id": str(entity_robert.id)},
            )
            assert survivor_rows[0]["merged_into"] is None
            assert survivor_rows[0]["merge_count"] >= 2
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) "
                "WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestTombstoneVectorSearchIntegration:
    """Regression coverage for an absorbed entity's embedding and vector search."""

    async def test_merged_entity_drops_out_of_vector_search(self) -> None:
        """A tombstoned entity's embedding must not keep it in vector search.

        ``tombstone_query`` used to only set ``merged_into``, leaving the
        absorbed node's domain label and embedding untouched. Neo4j's native
        vector index covers every node carrying the indexed property
        regardless of ``merged_into``, so a search could return an absorbed
        entity instead of, or alongside, its survivor.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        query_vector = [1.0, 0.0, 0.0, 0.0]
        try:
            entity_a = Entity(
                id=uuid4(), label=label, name="Ada Lovelace", embedding=query_vector
            )
            # Earlier created_at wins canonical selection, so this becomes
            # the merge survivor and entity_a is tombstoned into it.
            entity_b = Entity(
                id=uuid4(),
                label=label,
                name="A. Lovelace",
                embedding=[0.0, 1.0, 0.0, 0.0],
                created_at=entity_a.created_at - timedelta(minutes=5),
            )
            await store.upsert_nodes(
                label, [entity_a.to_node_record(), entity_b.to_node_record()]
            )
            await store.execute_write(merge_key_constraint_query(label))
            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=len(query_vector),
                distance=Distance.COSINE,
            )

            plan, _ = await compute_merge(
                existing_entities=[entity_a, entity_b], mentions=[], schema=schema
            )
            assert plan.survivor.id == entity_b.id
            assert plan.tombstone_ids == [entity_a.id]
            await apply_merge(plan, graph_store=store, schema=schema)

            # Deterministic, independent of index population lag: the
            # tombstone's embedding property itself must be gone.
            tombstone_row = (
                await store.execute_read(
                    f"MATCH (n:{label} {{id: $id}}) RETURN n.embedding AS embedding",
                    {"id": str(entity_a.id)},
                )
            )[0]
            assert tombstone_row["embedding"] is None

            # Query with the tombstone's own former embedding: if it were
            # still indexed, it would rank above the survivor's unrelated
            # vector. A generous limit means both nodes are candidates.
            hits = await _vector_search_with_retry(
                store, label=label, query_vector=query_vector, limit=5
            )
            hit_ids = {hit.id for hit in hits}
            assert entity_b.id in hit_ids
            assert entity_a.id not in hit_ids
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) "
                "WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestConcurrentEmbedDuringMergeIntegration:
    """Regression coverage for an embed write racing a concurrent merge."""

    async def test_resumed_embed_write_does_not_restore_tombstone_vector(
        self,
    ) -> None:
        """A stale embed write must not restore a vector a merge just cleared.

        Simulates the interleaving deterministically rather than with real
        concurrent tasks, which would be non-deterministic and flaky:

        1. Pause embedding -- capture the name/description an in-flight
           embed() call for entity_a would have read, before anything else
           happens.
        2. Apply a merge -- tombstone entity_a into entity_b, which sets
           entity_a.merged_into and removes entity_a.embedding.
        3. Resume the stale vector write -- run set_embedding_query directly
           with the pre-merge name/description, exactly as the paused
           embed() call would once it finally lands.

        Before the ``merged_into IS NULL`` guard, this write would succeed
        because entity_a's name/description had not changed, restoring its
        embedding and returning it to native vector search despite being
        absorbed.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        stale_vector = [1.0, 0.0, 0.0, 0.0]
        try:
            entity_a = Entity(id=uuid4(), label=label, name="Ada Lovelace")
            # Earlier created_at wins canonical selection, so this becomes
            # the merge survivor and entity_a is tombstoned into it.
            entity_b = Entity(
                id=uuid4(),
                label=label,
                name="A. Lovelace",
                embedding=[0.0, 1.0, 0.0, 0.0],
                created_at=entity_a.created_at - timedelta(minutes=5),
            )
            await store.upsert_nodes(
                label, [entity_a.to_node_record(), entity_b.to_node_record()]
            )
            await store.execute_write(merge_key_constraint_query(label))
            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=len(stale_vector),
                distance=Distance.COSINE,
            )

            # 1. Pause embedding: the in-flight call's own read of entity_a,
            # taken before the merge below runs.
            paused_embed_record = {
                "id": str(entity_a.id),
                "vector": stale_vector,
                "expected_name": entity_a.name,
                "expected_description": "",
            }

            # 2. Apply a merge: tombstones entity_a into entity_b.
            plan, _ = await compute_merge(
                existing_entities=[entity_a, entity_b], mentions=[], schema=schema
            )
            assert plan.survivor.id == entity_b.id
            assert plan.tombstone_ids == [entity_a.id]
            await apply_merge(plan, graph_store=store, schema=schema)

            # 3. Resume the stale vector write.
            await store.execute_write(
                set_embedding_query("embedding"), {"records": [paused_embed_record]}
            )

            tombstone_row = (
                await store.execute_read(
                    f"MATCH (n:{label} {{id: $id}}) RETURN n.embedding AS embedding",
                    {"id": str(entity_a.id)},
                )
            )[0]
            assert tombstone_row["embedding"] is None

            hits = await _vector_search_with_retry(
                store, label=label, query_vector=stale_vector, limit=5
            )
            hit_ids = {hit.id for hit in hits}
            assert entity_a.id not in hit_ids
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) "
                "WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            await store.close()
