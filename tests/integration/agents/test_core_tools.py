"""Exercise the task agent's memory and evidence tools against Neo4j."""

import json
from uuid import uuid4

from agrag.agents.tools.core import make_core_tools
from agrag.chunking import Chunker
from agrag.common.data_models.decision import DECISION_LABEL
from agrag.common.data_models.evidence import DiscoveryMode
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.task import EventKind
from agrag.graphdb import build_graph_store
from agrag.ingestion.graph import Graph
from agrag.memory import DecisionMemory, TaskMemory
from tests.integration.retrieval.evidence._corpus import (
    HARBOR_TEXT,
    BagOfWordsEmbedder,
    NoEntityExtractor,
    make_document,
)


async def test_core_memory_tools_read_write_and_review_persisted_data() -> None:  # noqa: PLR0915
    """Direct core tools return paged memory and persisted decision state."""
    run = uuid4().hex
    harbor_key = f"evidence://{run}/harbor"
    store = build_graph_store("neo4j")
    graph = await Graph.open(
        schema=GraphSchema(name="core-tools", version="1", entities=[], relations=[]),
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        extractor=NoEntityExtractor(),
        chunker=Chunker(size=60),
    )
    await store.execute_read("CALL db.awaitIndexes(60)")
    await graph.add(documents=[make_document(harbor_key, HARBOR_TEXT)])
    project_id = f"core-tools-{uuid4().hex}"
    task_name = f"task-{uuid4().hex}"
    memory = TaskMemory(store, project_id=project_id, agent_id="core-tools-test")
    decisions = DecisionMemory(store, project_id=project_id, agent_id="core-tools-test")
    tools, _ = make_core_tools(
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        scope=frozenset({harbor_key}),
        task_name=task_name,
        memory=memory,
        decisions=decisions,
        fetched_ids=[],
        fetched_outcomes=[],
        max_chars=12_000,
        max_tool_calls=30,
    )
    tool_by_name = {item.name: item for item in tools}
    try:
        assert (await memory.create_task(task_name, "Review source evidence.")).recorded
        task_view = json.loads(await tool_by_name["get_task"].ainvoke({}))
        assert task_view["found"] is True

        await memory.record_event(
            task_name, EventKind.NOTE, payload="first durable note"
        )
        event_two = await memory.record_event(
            task_name, EventKind.NOTE, payload="second durable note"
        )
        event_page = json.loads(
            await tool_by_name["list_events"].ainvoke(
                {"event_task_name": task_name, "after_seq": 0, "limit": 1}
            )
        )
        assert [event["payload"] for event in event_page["events"]] == [
            "first durable note"
        ]
        next_event_page = json.loads(
            await tool_by_name["list_events"].ainvoke(
                {"event_task_name": task_name, "after_seq": 1, "limit": 1}
            )
        )
        assert [event["payload"] for event in next_event_page["events"]] == [
            "second durable note"
        ]
        event_lookup = json.loads(
            await tool_by_name["get_event"].ainvoke(
                {"event_task_name": task_name, "seq": event_two.event.seq}
            )
        )
        assert event_lookup["event"]["payload"] == "second durable note"

        await tool_by_name["set_step"].ainvoke(
            {"name": "inspect source", "state_name": "in_progress", "kind": "read"}
        )
        await tool_by_name["set_step"].ainvoke(
            {"name": "write summary", "state_name": "in_progress", "kind": "analysis"}
        )
        step_page = json.loads(
            await tool_by_name["list_steps"].ainvoke(
                {"state_name": "in_progress", "limit": 1}
            )
        )
        assert [step["name"] for step in step_page["steps"]] == ["inspect source"]
        next_step_page = json.loads(
            await tool_by_name["list_steps"].ainvoke(
                {
                    "state_name": "in_progress",
                    "after_name": "inspect source",
                    "limit": 1,
                }
            )
        )
        assert [step["name"] for step in next_step_page["steps"]] == ["write summary"]

        found = json.loads(
            await tool_by_name["discover_evidence"].ainvoke(
                {"query": "harbor lighthouse", "mode": DiscoveryMode.LEXICAL.value}
            )
        )
        evidence_id = found["hits"][0]["evidence_id"]
        fetched = json.loads(
            await tool_by_name["fetch_evidence"].ainvoke(
                {"evidence_ids": [evidence_id]}
            )
        )
        assert fetched[0]["status"] == "ok"
        neighboring_passages = [
            json.loads(
                await tool_by_name["navigate_document_tree"].ainvoke(
                    {"evidence_id": evidence_id, "relation": relation}
                )
            )
            for relation in ("previous", "next")
        ]
        assert sum(len(result["items"]) for result in neighboring_passages) > 0
        malformed_navigation = json.loads(
            await tool_by_name["navigate_document_tree"].ainvoke(
                {"evidence_id": "not-an-evidence-id", "relation": "next"}
            )
        )
        assert malformed_navigation["status"] == "malformed"

        recorded = json.loads(
            await tool_by_name["record_decision"].ainvoke(
                {
                    "choice_key": "harbor-policy",
                    "conclusion": "Retain the harbor record.",
                    "rationale": "The current passage supports retention.",
                    "supports": [{"evidence_id": evidence_id}],
                }
            )
        )
        decision_id = recorded["decision"]["id"]
        assert recorded["recorded"] is True
        assert recorded["decision"]["supports"][0]["kind"] == "document"
        for invalid_limit in (0, 51):
            for name, arguments in (
                ("list_support_history", {"decision_id": decision_id}),
                ("list_decisions_for_review", {}),
            ):
                response = await tool_by_name[name].ainvoke(
                    {**arguments, "limit": invalid_limit}
                )
                assert response == "Limit must be between 1 and 50."
        fetched_decision = json.loads(
            await tool_by_name["get_decision"].ainvoke({"decision_id": decision_id})
        )
        assert fetched_decision["decision"]["conclusion"] == "Retain the harbor record."
        history = json.loads(
            await tool_by_name["list_support_history"].ainvoke(
                {"decision_id": decision_id, "limit": 1}
            )
        )
        assert history["supports"][0]["evidence_id"] == evidence_id

        malformed_history = await tool_by_name["list_support_history"].ainvoke(
            {"decision_id": "not-a-uuid"}
        )
        assert malformed_history == "decision_id must be a UUID."

        await graph.add(documents=[make_document(harbor_key, "Harbor record revised.")])
        review_page = json.loads(
            await tool_by_name["list_decisions_for_review"].ainvoke({"limit": 5})
        )
        assert [decision["id"] for decision in review_page["decisions"]] == [
            decision_id
        ]
        continuation = json.loads(
            await tool_by_name["continue_decision_review"].ainvoke({"limit": 5})
        )
        assert continuation["processed"] == 1
        refreshed_search = json.loads(
            await tool_by_name["discover_evidence"].ainvoke(
                {"query": "harbor revised", "mode": DiscoveryMode.LEXICAL.value}
            )
        )
        refreshed_id = refreshed_search["hits"][0]["evidence_id"]
        await tool_by_name["fetch_evidence"].ainvoke({"evidence_ids": [refreshed_id]})
        reaffirmed = json.loads(
            await tool_by_name["reaffirm_decision"].ainvoke(
                {
                    "decision_id": decision_id,
                    "evidence_ids": [refreshed_id],
                    "explanation": "Reviewed the revised passage.",
                }
            )
        )
        assert reaffirmed["recorded"] is True
        persisted = await decisions.get_decision(recorded["decision"]["id"])
        assert persisted.decision.review_state.value == "clear"
        assert persisted.decision.supports[0].evidence_id == refreshed_id

        listed = json.loads(await tool_by_name["list_decisions"].ainvoke({}))
        assert listed["page"]["decisions"][0]["id"] == decision_id
        await store.ensure_fulltext_index(
            label=DECISION_LABEL, properties=["conclusion", "rationale"]
        )
        await store.execute_read("CALL db.awaitIndexes(60)")
        precedent = json.loads(
            await tool_by_name["search_decisions"].ainvoke({"query": "Retain harbor"})
        )
        assert [hit["decision"]["id"] for hit in precedent] == [decision_id]
        completed = json.loads(
            await tool_by_name["set_step"].ainvoke(
                {
                    "name": "inspect source",
                    "state_name": "completed",
                    "kind": "read",
                    "result": "The retention decision has current support.",
                    "result_basis": "supported",
                    "supports": [{"decision_id": decision_id}],
                }
            )
        )
        assert completed["recorded"] is True
        assert completed["step"]["result_supports"][0]["kind"] == "decision"
        superseded = json.loads(
            await tool_by_name["supersede_decision"].ainvoke(
                {
                    "decision_id": decision_id,
                    "conclusion": "Review the revised harbor record.",
                    "rationale": "Replace the old retention instruction.",
                    "explanation": "The current passage needs a revised instruction.",
                    "supports": [{"evidence_id": refreshed_id}],
                }
            )
        )
        assert superseded["recorded"] is True
        old = json.loads(
            await tool_by_name["get_decision"].ainvoke({"decision_id": decision_id})
        )
        assert old["decision"]["status"] == "superseded"
    finally:
        await store.execute_write(
            "MATCH (d:MemoryDecision {project_id: $project_id}) "
            "OPTIONAL MATCH (d)-[:HAS_SUPPORT]->(s) DETACH DELETE s, d",
            {"project_id": project_id},
        )
        await store.execute_write(
            "MATCH (t:MemoryTask {project_id: $project_id}) "
            "OPTIONAL MATCH (t)-[:HAS_EVENT|HAS_STEP]->(child) "
            "DETACH DELETE child, t",
            {"project_id": project_id},
        )
        await store.execute_write(
            "MATCH (r:MemoryRequest {project_id: $project_id}) DETACH DELETE r",
            {"project_id": project_id},
        )
        await store.execute_write(
            "MATCH (p:MemoryProject {project_id: $project_id}) DETACH DELETE p",
            {"project_id": project_id},
        )
        prefix = f"evidence://{run}/"
        await store.execute_write(
            "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
            "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c, d",
            {"prefix": prefix},
        )
        await store.close()
