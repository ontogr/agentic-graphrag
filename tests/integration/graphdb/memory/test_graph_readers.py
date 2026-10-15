"""Integration tests that graph readers never return task memory nodes.

Task memory nodes do not carry the identity label that entity readers require,
and their relationship types are on the non-entity lists. A reader started from
a memory node must find nothing.
"""

from agrag.common.data_models.task import EventKind, StepState
from agrag.cypher.relations import bfs_expand_query, relationship_types_from_query
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory


class TestGraphReaders:
    """Entity-graph readers skip Project, Task, Event, Step and Request nodes."""

    async def test_readers_seeded_from_memory_nodes_return_nothing(
        self, store: GraphStore, project: str
    ) -> None:
        """Traversal and relation-type listings from memory ids are empty."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        task = await memory.create_task("graph facts", "Stay out of the graph")
        event = await memory.record_event(
            "graph facts", EventKind.MESSAGE, payload="hello"
        )
        step = await memory.set_step(
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
