"""Run the pinned connected-context workflow against a configured Neo4j graph."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from agrag.agents import AgentLLMSettings, AgentSettings, build_agent
from agrag.common.data_models.decision import DocumentSupport, DocumentSupportInput
from agrag.common.data_models.document import Document
from agrag.common.data_models.evidence import (
    EvidenceSearchMode,
    FetchOutcome,
    VersionStatus,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.task import (
    EventKind,
    StepKind,
    StepResultBasis,
    StepState,
)
from agrag.decisions import DecisionTraces
from agrag.embedding import build_embedder
from agrag.evidence import fetch_evidence, search_evidence
from agrag.graphdb import build_graph_store
from agrag.history import ConversationHistory
from agrag.ingestion import Graph
from benchmarks.datasets.base import text_document
from benchmarks.datasets.conversation_history import (
    load_rows,
    session_document_text,
    text_sha256,
)
from benchmarks.datasets.fetch import fetch_hf_file
from benchmarks.schemas.conversation_history import CONVERSATION_HISTORY
from benchmarks.schemas.legal import LEGAL


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "benchmarks/fixtures/connected_context/manifest.json"
FIXTURE = json.loads(MANIFEST.read_text(encoding="utf-8"))
DOCS = {item["uri"]: item for item in FIXTURE["documents"]}
PROJECT = "connected-context-example"
AGENT = "connected-context-example-agent"
KEEP = "privacy_qa/Keep.txt"
SCOPE = frozenset(DOCS)
MUTATION = FIXTURE["mutations"][0]


def _schema() -> GraphSchema:
    entities = {item.label: item for item in LEGAL.entities}
    entities.update({item.label: item for item in CONVERSATION_HISTORY.entities})
    relations = {item.label: item for item in LEGAL.relations}
    relations.update({item.label: item for item in CONVERSATION_HISTORY.relations})
    return GraphSchema(
        name="connected-context",
        version="1",
        entities=list(entities.values()),
        relations=list(relations.values()),
    )


def _documents() -> list[Document]:
    legal = []
    for uri in (
        KEEP,
        "privacy_qa/Viber Messenger.txt",
        "contractnli/Kenway-NDA-Form-Blank.txt",
    ):
        item = DOCS[uri]
        source = fetch_hf_file(
            "awinml/legalbench-rag",
            f"corpus/{uri}",
            revision=FIXTURE["upstream"]["legal"]["revision"],
            sha256=item["sha256"],
        ).read_text(encoding="utf-8")
        if hashlib.sha256(source.encode()).hexdigest() != item["content_sha256"]:
            raise ValueError(f"Pinned text hash mismatch: {uri}")
        legal.append(text_document(source, uri=uri))
    row = load_rows(["conversation_id", "chat"])["17"]
    history = []
    for uri, session_number, message_ids in (
        ("beam/17/session-1", 1, [18]),
        ("beam/17/session-3", 3, [156, 157]),
    ):
        source = session_document_text(
            row["chat"][session_number - 1], session_number, "17", message_ids
        )
        if text_sha256(source) != DOCS[uri]["content_sha256"]:
            raise ValueError(f"Pinned text hash mismatch: {uri}")
        history.append(text_document(source, uri=uri))
    return [*legal, *history]


def _agent(store: Any, embedder: Any, *, project_id: str = PROJECT) -> Any:
    return build_agent(
        graph_store=store,
        embedder=embedder,
        scope=SCOPE,
        project_id=project_id,
        agent_id=AGENT,
        llm_settings=AgentLLMSettings.from_openai_compatible_env(),
        agent_settings=AgentSettings(),
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _fixture_support(store: Any, support: dict[str, Any]) -> FetchOutcome:
    """Fetch a pinned passage for deterministic checkpoint and review setup."""
    key = support["document"]
    evidence_id = (
        f"ev1:s:{Document.node_id_for(document_key=key)}:"
        f"{DOCS[key]['content_sha256'][:16]}:"
        f"{support['char_start']}-{support['char_end']}"
    )
    [outcome] = await fetch_evidence(
        store, [evidence_id], scope=SCOPE, max_chars=12_000
    )
    _require(outcome.status.value == "ok", f"fixture passage unavailable: {key}")
    return outcome


async def ingest() -> dict[str, Any]:
    """Ingest the five pinned source documents using configured extraction."""
    store = build_graph_store("neo4j")
    embedder = build_embedder("ibm-granite/granite-embedding-small-english-r2")
    graph = await Graph.open(
        schema=_schema(), graph_store=store, embedder=embedder, max_llm_pairs=0
    )
    try:
        result = await graph.add(documents=_documents())
        return {
            "stage": "ingest",
            "document_count": len(DOCS),
            "result": result.model_dump(mode="json"),
        }
    finally:
        await store.close()


async def _ask(agent: Any, name: str, question: str) -> dict[str, Any]:
    result = await agent.ainvoke({"task_name": name, "question": question})
    _require(
        result["status"] in {"answered", "insufficient_evidence"},
        f"{name}: {result['status']}",
    )
    _require(not result["invalid_citations"], f"{name}: invalid citations")
    return {
        "task": name,
        "question": question,
        "status": result["status"],
        "answer": result["answer"],
        "citations": [item.model_dump(mode="json") for item in result["citations"]],
        "semantic_expected_facts": [],
    }


async def _replace_source(store: Any, embedder: Any) -> dict[str, Any]:
    source = next(document.text for document in _documents() if document.uri == KEEP)
    edit = MUTATION["edit"]
    _require(
        source[edit["char_start"] :].startswith(edit["old"]),
        "M1 source offset mismatch",
    )
    changed = (
        source[: edit["char_start"]]
        + edit["new"]
        + source[edit["char_start"] + len(edit["old"]) :]
    )
    _require(
        hashlib.sha256(changed.encode()).hexdigest() == MUTATION["content_sha256"],
        "M1 hash mismatch",
    )
    graph = await Graph.open(
        schema=_schema(), graph_store=store, embedder=embedder, max_llm_pairs=0
    )
    outcome = await graph.add(documents=[text_document(changed, uri=KEEP)])
    return {
        "mutation": "M1",
        "sha256": hashlib.sha256(changed.encode()).hexdigest(),
        "ingestion": outcome.model_dump(mode="json"),
    }


async def exercise() -> dict[str, Any]:  # noqa: PLR0912, PLR0915
    """Run six model-backed cases, controls, source review and holdout queries."""
    store = build_graph_store("neo4j")
    await store.connect()
    embedder = build_embedder("ibm-granite/granite-embedding-small-english-r2")
    agent = _agent(store, embedder)
    tasks = ConversationHistory(store, project_id=PROJECT, agent_id=AGENT)
    decisions = DecisionTraces(store, project_id=PROJECT, agent_id=AGENT)
    cases: dict[str, Any] = {}
    try:
        configured = [
            item
            for item in FIXTURE["cases"]
            if item["id"] not in {"source_change_review", "interruption_and_resume"}
        ]
        for case in configured:
            case_id = case["id"]
            if case_id == "cross_session_recall":
                answers = []
                for item in case["questions"]:
                    answer = await _ask(
                        agent, f"{case_id}-{len(answers)}", item["question"]
                    )
                    answer["semantic_expected_facts"] = item["rubric"]
                    cited_keys = {
                        citation["document_key"] for citation in answer["citations"]
                    }
                    _require(
                        item["support_document"] in cited_keys,
                        "recall citation missed its source",
                    )
                    _require(
                        not cited_keys.intersection(item["must_not_cite"]),
                        "recall cited forbidden session",
                    )
                    answers.append(answer)
                cases[case_id] = answers
                continue
            question = case["question"]
            answer = await _ask(agent, case_id, question)
            if case_id == "insufficient_evidence":
                _require(
                    answer["status"] == "insufficient_evidence",
                    "unanswerable case did not abstain",
                )
                _require(not answer["citations"], "unanswerable case cited evidence")
            else:
                expected_docs = {support["document"] for support in case["support"]}
                cited_docs = {
                    citation["document_key"] for citation in answer["citations"]
                }
                _require(
                    expected_docs.issubset(cited_docs),
                    f"{case_id} missed expected source citation",
                )
                answer["semantic_expected_facts"] = [
                    support["answer"] for support in case["support"]
                ]
            cases[case_id] = answer

        resume_case = next(
            item for item in FIXTURE["cases"] if item["id"] == "interruption_and_resume"
        )
        resume_task = "interruption_and_resume"
        cases[resume_task] = {}
        _require(
            (await tasks.create_task(resume_task, resume_case["question"])).recorded,
            "resume task create failed",
        )
        checkpoint_support = await _fixture_support(store, resume_case["support"][0])
        if checkpoint_support.text is None:
            raise AssertionError("checkpoint passage has no text")
        checkpoint = await tasks.record_event(
            resume_task, EventKind.NOTE, payload=checkpoint_support.text
        )
        if not checkpoint.recorded or checkpoint.event is None:
            raise AssertionError("checkpoint failed")
        _require(
            (
                await tasks.set_step(
                    resume_task,
                    "A",
                    StepState.COMPLETED,
                    kind=StepKind.READ,
                    result_event_seq=checkpoint.event.seq,
                    result_basis=StepResultBasis.SUPPORTED,
                    supports=[
                        DocumentSupportInput(evidence_id=checkpoint_support.evidence_id)
                    ],
                    fetched_evidence=[checkpoint_support],
                )
            ).recorded,
            "resume checkpoint failed",
        )
        _require(
            (
                await tasks.set_step(
                    resume_task, "B", StepState.IN_PROGRESS, kind=StepKind.READ
                )
            ).recorded,
            "resume pending step failed",
        )
        resumed = await _ask(agent, resume_task, resume_case["question"])
        view = await tasks.get_task(resume_task)
        if view.view is None:
            raise AssertionError("resumed task is missing")
        _require(
            view.view.step_counts[StepState.COMPLETED] >= 1,
            "resume lost completed work",
        )
        cases["interruption_and_resume"]["resumed"] = resumed
        cases["interruption_and_resume"]["semantic_expected_facts"] = [
            support["answer"] for support in resume_case["support"]
        ]
        cases["interruption_and_resume"]["persisted_task"] = view.view.model_dump(
            mode="json"
        )

        source_case = next(
            item for item in FIXTURE["cases"] if item["id"] == "source_change_review"
        )
        baseline = await _ask(
            agent, "source_change_review", source_case["decisions"]["D1"]
        )
        support = await _fixture_support(
            store, next(item for item in source_case["support"] if item["role"] == "D1")
        )
        record = await decisions.record_decision(
            "source_change_review",
            "keep-sale-policy",
            source_case["decisions"]["D1"],
            "The current policy says personal information is not sold.",
            supports=[DocumentSupportInput(evidence_id=support.evidence_id)],
            fetched_evidence=[support],
            request_id="connected-context-decision-v1",
        )
        if not record.recorded or record.decision is None:
            raise AssertionError(f"decision record failed: {record.error}")
        original = record.decision
        mutation = await _replace_source(store, embedder)
        review = await decisions.list_decisions_for_review(
            task_name="source_change_review"
        )
        _require(
            any(item.id == original.id for item in review.decisions),
            "M1 did not flag source-backed decision",
        )
        current = await fetch_evidence(
            store, [support.evidence_id], scope=SCOPE, max_chars=12_000
        )
        _require(
            bool(current) and current[0].status_of_version is VersionStatus.SUPERSEDED,
            "old evidence was not marked superseded after M1",
        )
        stale_reaffirm = await decisions.reaffirm_decision(
            original.id,
            [DocumentSupportInput(evidence_id=support.evidence_id)],
            fetched_evidence=current,
        )
        _require(not stale_reaffirm.recorded, "stale support was accepted after M1")
        search = await search_evidence(
            store,
            embedder,
            "Keep personal information sale share advertising partners",
            mode=EvidenceSearchMode.HYBRID,
            limit=10,
            scope=frozenset({KEEP}),
        )
        _require(bool(search.hits), "M1 current evidence search returned no passages")
        current_fetches = await fetch_evidence(
            store,
            [hit.evidence_id for hit in search.hits],
            scope=frozenset({KEEP}),
            max_chars=12_000,
        )
        current_support = next(
            (
                item
                for item in current_fetches
                if item.status.value == "ok"
                and item.text is not None
                and "advertising partners" in item.text
            ),
            None,
        )
        _require(current_support is not None, "could not fetch current M1 passage")
        revised = await _ask(
            agent,
            "source_change_review",
            "The Keep source has changed. Inspect decisions needing review, advance "
            "queued review propagation until complete, fetch the current policy, "
            "and explicitly supersede keep-sale-policy if its no-sale conclusion "
            "is no longer supported. Do not reaffirm a changed conclusion. "
            "Explain the current policy with citations.",
        )
        source_change = await decisions.get_decision(original.id)
        _require(
            source_change.decision is not None
            and source_change.decision.status.value == "superseded",
            "agent did not supersede the outdated decision",
        )
        history = await decisions.list_support_history(original.id)
        _require(
            any(
                isinstance(item, DocumentSupport)
                and item.evidence_id == support.evidence_id
                for item in history.supports
            ),
            "support history did not retain original evidence",
        )
        cases["source_change_review"] = {
            "baseline": baseline,
            "decision": original.model_dump(mode="json"),
            "mutation": mutation,
            "review_flagged": True,
            "revised": revised,
            "support_history": history.model_dump(mode="json"),
            "current_decision": source_change.decision.model_dump(mode="json")
            if source_change.decision
            else None,
            "semantic_expected_facts": [
                "updated policy permits sharing personal information "
                "with advertising partners"
            ],
        }

        controls = {}
        recall = next(
            item for item in FIXTURE["cases"] if item["id"] == "cross_session_recall"
        )
        for item in recall["questions"]:
            fresh_project = f"connected-context-fresh-{uuid4().hex}"
            fresh_agent = _agent(store, embedder, project_id=fresh_project)
            clean = await _ask(
                fresh_agent, f"fresh-{uuid4().hex[:8]}", item["question"]
            )
            controls[item["question_id"]] = {
                "answer": clean,
                "expected_fact": item["rubric"],
                "no_prior_task_or_decision_history": True,
            }

        variations = []
        for case in FIXTURE["cases"]:
            holdout = case.get("holdout", {})
            question = holdout.get("question")
            if question:
                result = await _ask(agent, f"variation-{case['id']}", question)
                result["semantic_expected_facts"] = [
                    support["answer"]
                    for support in case.get("support", [])
                    if "answer" in support
                ]
                variations.append(result)

        return {
            "stage": "exercise",
            "cases": cases,
            "fresh_state_controls": controls,
            "final_unseen_variations": variations,
            "assertions": "passed",
        }
    finally:
        await store.close()


async def mcp() -> dict[str, Any]:
    """Exercise scoped evidence and decision review tools through stdio MCP."""
    from mcp import ClientSession, StdioServerParameters  # noqa: PLC0415
    from mcp.client.stdio import stdio_client  # noqa: PLC0415

    environment = os.environ.copy()
    environment.update(
        {
            "MCP_SCOPE_DOCUMENT_KEYS": ",".join(sorted(SCOPE)),
            "MCP_PROJECT_ID": PROJECT,
            "MCP_AGENT_ID": AGENT,
            "MCP_READ_ONLY": "false",
        }
    )
    async with (
        stdio_client(
            StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "agrag.mcp_server"],
                env=environment,
            )
        ) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        available = {tool.name for tool in (await session.list_tools()).tools}
        needed = {
            "create_task",
            "search_evidence",
            "fetch_evidence",
            "list_decisions_for_review",
            "record_decision",
            "reaffirm_decision",
        }
        _require(
            needed.issubset(available),
            f"MCP tools missing: {sorted(needed - available)}",
        )
        search_result = await session.call_tool(
            "search_evidence",
            {
                "query": "Keep personal information advertising partners",
                "mode": "hybrid",
                "limit": 5,
            },
        )
        hits = search_result.structured_content["hits"]
        _require(bool(hits), "MCP evidence search returned no hits")
        fetched = await session.call_tool(
            "fetch_evidence", {"evidence_ids": [hits[0]["evidence_id"]]}
        )
        _require(not fetched.is_error, "MCP evidence fetch failed")
        hit_fetch = fetched.structured_content["outcomes"][0]
        _require(hit_fetch["status"] == "ok", "MCP did not return fetched evidence")
        task = await session.call_tool(
            "create_task",
            {
                "task_name": "mcp-review-check",
                "goal": "Review the current sharing policy.",
                "request_id": "connected-context-mcp-task",
            },
        )
        _require(
            not task.is_error and task.structured_content["recorded"],
            "MCP task creation failed",
        )
        created = await session.call_tool(
            "record_decision",
            {
                "task_name": "mcp-review-check",
                "choice_key": "current-policy",
                "conclusion": "The current passage describes the sharing policy.",
                "rationale": "Recorded from evidence fetched in this stdio session.",
                "supports": [{"evidence_id": hit_fetch["evidence_id"]}],
                "request_id": "connected-context-mcp-decision",
                "assumptions": [],
                "open_questions": [],
            },
        )
        _require(
            not created.is_error and created.structured_content["recorded"],
            "MCP decision write failed",
        )
        decision_id = created.structured_content["decision"]["id"]
        reaffirmed = await session.call_tool(
            "reaffirm_decision",
            {
                "decision_id": decision_id,
                "evidence_ids": [hit_fetch["evidence_id"]],
                "explanation": "Rechecked the currently fetched source passage.",
                "request_id": "connected-context-mcp-reaffirm",
            },
        )
        _require(
            not reaffirmed.is_error and reaffirmed.structured_content["recorded"],
            "MCP decision reaffirm failed",
        )
        reviews = await session.call_tool(
            "list_decisions_for_review", {"task_name": "source_change_review"}
        )
        _require(not reviews.is_error, "MCP review listing failed")
        return {
            "stage": "mcp",
            "tool_names": sorted(available),
            "search": search_result.structured_content,
            "fetch": fetched.structured_content,
            "decision": created.structured_content,
            "reaffirmation": reaffirmed.structured_content,
            "review": reviews.structured_content,
            "write_tools_enabled": True,
            "assertions": "passed",
        }


async def main() -> None:
    """Run one workflow stage and save its structured result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("ingest", "exercise", "mcp"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = await {"ingest": ingest, "exercise": exercise, "mcp": mcp}[args.stage]()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.stage} result to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
