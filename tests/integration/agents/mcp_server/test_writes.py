"""Exercise task and decision tools through the in-memory MCP client.

The test uses the isolated integration Neo4j service and a unique project id.
It checks tool discovery, authorization, event persistence and retry behavior
through the same public client calls used by an MCP host.
"""

import hashlib
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from mcp import Client

from agrag.common.data_models.task import EventKind
from agrag.mcp_server.server import build_server
from agrag.mcp_server.settings import McpServerSettings
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


@pytest.fixture
async def memory_identity(
    evidence_env: EvidenceEnv,
) -> AsyncIterator[tuple[str, str]]:
    """Create a project identity and remove only its memory nodes afterwards."""
    project_id = f"mcp-{uuid4().hex}"
    agent_id = f"agent-{uuid4().hex}"
    try:
        yield project_id, agent_id
    finally:
        await evidence_env.store.execute_write(
            "MATCH (d:MemoryDecision {project_id: $project_id}) "
            "OPTIONAL MATCH (d)-[:HAS_SUPPORT]->(s) DETACH DELETE s, d",
            {"project_id": project_id},
        )
        await evidence_env.store.execute_write(
            "MATCH (t:MemoryTask {project_id: $project_id}) "
            "OPTIONAL MATCH (t)-[:HAS_EVENT|HAS_STEP]->(child) "
            "DETACH DELETE child, t",
            {"project_id": project_id},
        )
        await evidence_env.store.execute_write(
            "MATCH (r:MemoryRequest {project_id: $project_id}) DETACH DELETE r",
            {"project_id": project_id},
        )
        await evidence_env.store.execute_write(
            "MATCH (p:MemoryProject {project_id: $project_id}) DETACH DELETE p",
            {"project_id": project_id},
        )


class TestMcpMemoryTools:
    """MCP memory writes preserve scope, authority and retry guarantees."""

    async def test_tools_persist_scoped_events_and_gate_rejection(  # noqa: PLR0915
        self,
        evidence_env: EvidenceEnv,
        memory_identity: tuple[str, str],
    ) -> None:
        """Write tools persist events, while settings control each write gate."""
        project_id, agent_id = memory_identity
        base = McpServerSettings(
            scope_document_keys=evidence_env.keep,
            project_id=project_id,
            agent_id=agent_id,
            read_only=False,
        )
        server = build_server(evidence_env.store, BagOfWordsEmbedder(), base)

        async with Client(server) as client:
            tool_list = await client.list_tools()
            names = {tool.name for tool in tool_list.tools}
            create_schema = next(
                tool.input_schema
                for tool in tool_list.tools
                if tool.name == "create_task"
            )
            assert "project_id" not in create_schema["properties"]
            assert "agent_id" not in create_schema["properties"]
            decision_schema = next(
                tool.input_schema
                for tool in tool_list.tools
                if tool.name == "record_decision"
            )
            assert "fetched_evidence" not in decision_schema["properties"]
            tool_by_name = {tool.name: tool for tool in tool_list.tools}
            assert tool_by_name["create_task"].annotations.read_only_hint is False
            assert tool_by_name["get_task"].annotations.read_only_hint is True
            assert {
                "create_task",
                "record_event",
                "set_step",
                "get_task",
                "list_events",
                "fetch_event",
                "record_decision",
                "supersede_decision",
                "search_decisions",
                "list_conflicts",
                "get_decision",
            } <= names
            assert "reject_decision" not in names
            create = await client.call_tool(
                "create_task",
                {
                    "name": "mcp task",
                    "goal": "record an event",
                    "request_id": "create-once",
                },
            )
            assert create.structured_content["recorded"] is True
            assert create.structured_content["task"]["author"] == agent_id
            event_arguments = {
                "task_name": "mcp task",
                "kind": EventKind.MESSAGE.value,
                "payload": "event from the MCP host",
                "request_id": "event-once",
                "role": "user",
            }
            first = await client.call_tool("record_event", event_arguments)
            retry = await client.call_tool("record_event", event_arguments)
            event = first.structured_content["event"]
            assert event["seq"] == 1
            assert event["payload"] == "event from the MCP host"
            assert retry.structured_content == first.structured_content
            reused_request = await client.call_tool(
                "record_event",
                {**event_arguments, "payload": "different event body"},
            )
            assert reused_request.structured_content["recorded"] is False
            assert reused_request.structured_content["error"] == "request_id_reused"
            long_payload = "x" * 32_001
            long_event = await client.call_tool(
                "record_event",
                {
                    "task_name": "mcp task",
                    "kind": "tool_result",
                    "payload": long_payload,
                    "request_id": "long-event-once",
                    "name": "search",
                },
            )
            assert long_event.structured_content["event"]["truncated"] is True
            assert long_event.structured_content["event"]["payload_sha256"] == (
                hashlib.sha256(long_payload.encode()).hexdigest()
            )
            tool_call = await client.call_tool(
                "record_event",
                {
                    "task_name": "mcp task",
                    "kind": "tool_call",
                    "payload": "search for the recorded event",
                    "request_id": "tool-call-once",
                    "name": "search",
                },
            )
            assert tool_call.structured_content["event"]["kind"] == "tool_call"
            listed = await client.call_tool(
                "list_events", {"task_name": "mcp task", "limit": 5}
            )
            assert [item["seq"] for item in listed.structured_content["events"]] == [
                1,
                2,
                3,
            ]
            fetched = await client.call_tool(
                "fetch_event", {"task_name": "mcp task", "seq": 1}
            )
            assert fetched.structured_content["events"][0]["payload"] == (
                "event from the MCP host"
            )
            evidence_search = await client.call_tool(
                "search_evidence",
                {
                    "query": "keep upload activity database",
                    "mode": "lexical",
                    "limit": 1,
                },
            )
            evidence_id = evidence_search.structured_content["hits"][0]["evidence_id"]
            missing_fetch = await client.call_tool(
                "record_decision",
                {
                    "task_name": "mcp task",
                    "choice_key": "unfetched-support",
                    "conclusion": "Reject this write.",
                    "rationale": "The evidence was not fetched.",
                    "supports": [{"evidence_id": evidence_id}],
                    "assumptions": [],
                    "open_questions": [],
                    "request_id": "unfetched-decision",
                },
            )
            assert missing_fetch.structured_content["recorded"] is False
            assert missing_fetch.structured_content["error"] == "support_not_fetched"
            evidence_fetch = await client.call_tool(
                "fetch_evidence", {"evidence_ids": [evidence_id]}
            )
            assert evidence_fetch.structured_content["outcomes"][0]["status"] == "ok"
            step = await client.call_tool(
                "set_step",
                {
                    "task_name": "mcp task",
                    "name": "capture event",
                    "state": "completed",
                    "result_event_seq": 1,
                    "request_id": "step-once",
                },
            )
            assert step.structured_content["recorded"] is True
            task_view = await client.call_tool("get_task", {"name": "mcp task"})
            assert task_view.structured_content["found"] is True
            decision = await client.call_tool(
                "record_decision",
                {
                    "task_name": "mcp task",
                    "choice_key": "store-event",
                    "conclusion": "Keep the event",
                    "rationale": "The recorded event supports this choice.",
                    "supports": [
                        {"task_name": "mcp task", "seq": 1},
                        {"evidence_id": evidence_id},
                    ],
                    "assumptions": [],
                    "open_questions": [],
                    "request_id": "decision-once",
                },
            )
            decision_id = decision.structured_content["decision"]["id"]
            replacement = await client.call_tool(
                "supersede_decision",
                {
                    "decision_id": decision_id,
                    "conclusion": "Keep the event after review",
                    "rationale": "The event remains relevant.",
                    "explanation": "Clarified the decision.",
                    "supports": [{"task_name": "mcp task", "seq": 1}],
                    "assumptions": [],
                    "open_questions": [],
                    "request_id": "decision-replacement",
                },
            )
            assert replacement.structured_content["recorded"] is True
            original = await client.call_tool(
                "get_decision", {"decision_id": decision_id}
            )
            assert original.structured_content["decision"]["status"] == "superseded"
            decision_id = replacement.structured_content["decision"]["id"]
            other_task = await client.call_tool(
                "create_task",
                {
                    "name": "another task",
                    "goal": "compare the decision",
                    "request_id": "other-task-once",
                },
            )
            assert other_task.structured_content["recorded"] is True
            conflict_decision = await client.call_tool(
                "record_decision",
                {
                    "task_name": "another task",
                    "choice_key": "store-event",
                    "conclusion": "Do not keep the event",
                    "rationale": "The contrary decision is a precedent.",
                    "supports": [{"task_name": "mcp task", "seq": 1}],
                    "assumptions": [],
                    "open_questions": [],
                    "request_id": "conflict-decision-once",
                },
            )
            assert conflict_decision.structured_content["recorded"] is True
            conflicts = await client.call_tool("list_conflicts", {})
            assert conflicts.structured_content["groups"][0]["choice_key"] == (
                "store-event"
            )
            precedents = await client.call_tool(
                "search_decisions", {"query": "Keep", "limit": 5}
            )
            assert precedents.structured_content["result"]
            denied_reject = await client.call_tool(
                "reject_decision",
                {
                    "decision_id": decision_id,
                    "reason": "Not operator authorized",
                    "request_id": "reject-denied",
                },
            )
            assert denied_reject.is_error is True
            still_active = await client.call_tool(
                "get_decision", {"decision_id": decision_id}
            )
            assert still_active.structured_content["decision"]["status"] == "active"

        read_only = base.model_copy(update={"read_only": True})
        async with Client(
            build_server(evidence_env.store, BagOfWordsEmbedder(), read_only)
        ) as client:
            hidden = await client.list_tools()
            assert "record_event" not in {tool.name for tool in hidden.tools}
            denied = await client.call_tool(
                "record_event",
                {
                    "task_name": "mcp task",
                    "kind": "note",
                    "payload": "must not be written",
                    "request_id": "denied-write",
                },
            )
            assert denied.is_error is True
            existing = await client.call_tool(
                "list_events", {"task_name": "mcp task", "limit": 5}
            )
            assert len(existing.structured_content["events"]) == 3

        other_scope = read_only.model_copy(
            update={"project_id": f"other-{uuid4().hex}"}
        )
        async with Client(
            build_server(evidence_env.store, BagOfWordsEmbedder(), other_scope)
        ) as client:
            hidden_task = await client.call_tool("get_task", {"name": "mcp task"})
            assert hidden_task.structured_content["found"] is False
            hidden_events = await client.call_tool(
                "list_events", {"task_name": "mcp task", "limit": 5}
            )
            assert hidden_events.structured_content["found"] is False
            hidden_decision = await client.call_tool(
                "get_decision", {"decision_id": decision_id}
            )
            assert hidden_decision.structured_content["found"] is False

        reject_enabled = base.model_copy(update={"allow_reject": True})
        async with Client(
            build_server(evidence_env.store, BagOfWordsEmbedder(), reject_enabled)
        ) as client:
            reject_tools = await client.list_tools()
            assert "reject_decision" in {tool.name for tool in reject_tools.tools}
            assert (
                next(
                    tool
                    for tool in reject_tools.tools
                    if tool.name == "reject_decision"
                ).annotations.destructive_hint
                is True
            )
            rejected = await client.call_tool(
                "reject_decision",
                {
                    "decision_id": decision_id,
                    "reason": "The decision is no longer accepted.",
                    "request_id": "reject-once",
                },
            )
            assert rejected.structured_content["recorded"] is True
            persisted = await client.call_tool(
                "get_decision", {"decision_id": decision_id}
            )
            assert persisted.structured_content["decision"]["status"] == "rejected"
