"""Integration tests for history isolation from generic knowledge graph labels."""

from uuid import uuid4

from agrag.common.data_models.decision import EventSupportInput
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.evidence import EvidenceSearchMode
from agrag.common.data_models.task import EventKind, StepState
from agrag.cypher.relations import bfs_expand_query, relationship_types_from_query
from agrag.decisions import DecisionTraces
from agrag.evidence import entity_search
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory
from tests.integration._backend import await_indexes
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder


class TestGraphReaders:
    """Entity readers distinguish history records from knowledge entities."""

    async def test_readers_seeded_from_history_nodes_return_nothing(
        self, store: GraphStore, project: str
    ) -> None:
        """Traversal and relation-type listings from history ids are empty."""
        history = ConversationHistory(store, project_id=project, agent_id="agent-a")
        task = await history.create_task("graph facts", "Stay out of the graph")
        event = await history.record_event(
            "graph facts", EventKind.MESSAGE, payload="hello"
        )
        step = await history.set_step(
            "graph facts", "one step", StepState.COMPLETED, result_event_seq=1
        )
        assert task.task is not None
        assert event.event is not None
        assert step.step is not None
        seeds = [str(task.task.id), str(event.event.id), str(step.step.id)]

        traversal, traversal_params = bfs_expand_query(depth=3, limit=50)
        neighbors = await store.execute_read(
            traversal, {**traversal_params, "seed_ids": seeds, "job_id": None}
        )
        relation_types = await store.execute_read(
            relationship_types_from_query(),
            {"seed_ids": seeds, "job_id": None},
        )
        identity_nodes = await store.execute_read(
            "UNWIND $ids AS id OPTIONAL MATCH (n:_Node {id: id}) "
            "RETURN count(n) AS found",
            {"ids": seeds},
        )

        assert neighbors == []
        assert relation_types == []
        assert identity_nodes == [{"found": 0}]

    async def test_generic_entity_labels_coexist_with_history_records(
        self, store: GraphStore, project: str, documents
    ) -> None:
        """Shared event keys coexist while unrelated decision hits stay isolated."""
        suffix = uuid4().hex[:8]
        history = ConversationHistory(store, project_id=project, agent_id="agent")
        task_write = await history.create_task("coexist", "Check generic labels")
        assert task_write.task is not None
        event_entity = Entity(
            id=uuid4(),
            label="Event",
            name=f"knowledge event {suffix}",
            properties={"task_id": str(task_write.task.id), "seq": 1},
        )
        decision_entity = Entity(
            id=uuid4(),
            label="Decision",
            name=f"knowledge decision {suffix}",
            properties={
                "conclusion": f"coexistence decision {suffix}",
                "rationale": f"knowledge rationale {suffix}",
            },
        )
        entity_ids = [str(event_entity.id), str(decision_entity.id)]
        try:
            await store.ensure_fulltext_index(label="Event", properties=["name"])
            await store.ensure_fulltext_index(label="Decision", properties=["name"])
            await store.upsert_nodes("Event", [event_entity.to_node_record()])

            event_write = await history.record_event(
                "coexist",
                EventKind.TOOL_RESULT,
                name=f"knowledge event {suffix}",
                payload=f"history event {suffix}",
            )
            assert event_write.event is not None
            assert event_entity.properties["task_id"] == str(event_write.event.task_id)
            assert event_entity.properties["seq"] == event_write.event.seq

            decisions = DecisionTraces(store, project_id=project, agent_id="agent")
            decision_write = await decisions.record_decision(
                "coexist",
                "coexistence",
                f"coexistence decision {suffix}",
                f"history rationale {suffix}",
                supports=[
                    EventSupportInput(task_name="coexist", seq=event_write.event.seq)
                ],
            )
            assert decision_write.decision is not None
            await store.upsert_nodes("Decision", [decision_entity.to_node_record()])

            chunk_rows = await store.execute_read(
                "MATCH (d:_Node:Document {document_key: $document_key}) "
                "-[:HAS_PART]->(c:_Node:Chunk) RETURN c.id AS id LIMIT 1",
                {"document_key": documents.keep},
            )
            assert chunk_rows
            await store.execute_write(
                "MATCH (c:_Node {id: $chunk_id}), (e:_Node {id: $event_id}), "
                "(d:_Node {id: $decision_id}) "
                "CREATE (c)-[:MENTIONED_IN]->(e) "
                "CREATE (c)-[:MENTIONED_IN]->(d)",
                {
                    "chunk_id": chunk_rows[0]["id"],
                    "event_id": str(event_entity.id),
                    "decision_id": str(decision_entity.id),
                },
            )
            await await_indexes(store)

            event_entity_search = await entity_search(
                store,
                BagOfWordsEmbedder(),
                f"knowledge event {suffix}",
                scope=frozenset({documents.keep}),
                labels=["Event"],
                limit=5,
                mode=EvidenceSearchMode.LEXICAL,
            )
            decision_entity_search = await entity_search(
                store,
                BagOfWordsEmbedder(),
                f"knowledge decision {suffix}",
                scope=frozenset({documents.keep}),
                labels=["Decision"],
                limit=5,
                mode=EvidenceSearchMode.LEXICAL,
            )
            stored_events = await history.list_events("coexist")
            decision_search = await decisions.search_decisions(
                f"coexistence decision {suffix}"
            )
            decision_search_call = await store.fulltext_search_call(
                label="Decision", properties=["conclusion", "rationale"]
            )
            fulltext_hits = await store.execute_read(
                f"{decision_search_call.text} RETURN node.id AS id",
                {
                    **decision_search_call.params,
                    "fulltext_terms": f"coexistence decision {suffix}",
                    "k": 10,
                },
            )

            assert [hit.entity_id for hit in event_entity_search.hits] == [
                str(event_entity.id)
            ]
            assert [hit.entity_id for hit in decision_entity_search.hits] == [
                str(decision_entity.id)
            ]
            assert [event.id for event in stored_events.events] == [
                event_write.event.id
            ]
            assert str(decision_entity.id) in {row["id"] for row in fulltext_hits}
            assert [hit.decision.id for hit in decision_search] == [
                decision_write.decision.id
            ]
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n", {"ids": entity_ids}
            )
