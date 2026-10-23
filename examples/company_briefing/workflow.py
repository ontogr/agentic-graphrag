"""Run a staged company briefing against a disposable Neo4j graph."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agrag.agents import AgentLLMSettings, AgentSettings, build_agent
from agrag.common.data_models.decision import DocumentSupportInput, ReviewState
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    DocumentSection,
    SourceFormat,
    Unit,
    UnitKind,
)
from agrag.common.data_models.evidence import (
    EvidenceSearchMode,
    FetchOutcome,
    FetchStatus,
)
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.common.data_models.navigation import NavigationRelation
from agrag.decisions import DecisionTraces
from agrag.embedding import build_embedder
from agrag.embedding.base import Embedder
from agrag.evidence import (
    entity_search,
    explore_relationships,
    fetch_evidence,
    navigate_document_tree,
    search_evidence,
)
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory
from agrag.ingestion import ExtractionSettings, Graph
from agrag.ingestion.reports import AddResult
from agrag.loaders.docling import DoclingPdfLoader
from agrag.loaders.types import ReadOptions, SourceRef


ROOT = Path(__file__).resolve().parents[2]
SOURCE = json.loads(
    (ROOT / "examples/company_briefing/sources.json").read_text(encoding="utf-8")
)["sources"][0]
DATA_DIR = Path(
    os.environ.get(
        "AGRAG_EXAMPLE_DATA_DIR",
        str(Path.home() / ".cache/agentic-graphrag/company-briefing"),
    )
).expanduser()
DOCUMENT_KEY = SOURCE["document_key"]
PROJECT_ID = "company-briefing-demo"
AGENT_ID = "company-briefing-agent"
TASK_NAME = "boeing-fy2022-briefing"
EMBEDDING_MODEL = "ibm-granite/granite-embedding-small-english-r2"
RISK_ANCHOR = "airline industry has been cyclical and very competitive"
AIRLINE_REVENUE_ANCHOR = "limited number of commercial airlines"


def _schema() -> GraphSchema:
    """Describe the company, segment, industry, and reported-revenue entities."""
    return GraphSchema(
        name="company-briefing",
        version="1",
        entities=[
            EntityType(
                label="Company",
                description="The company that is the subject of the annual report.",
            ),
            EntityType(
                label="BusinessSegment",
                description=(
                    "A reportable business segment named in the filing. Preserve "
                    "the filing's exact segment name."
                ),
            ),
            EntityType(
                label="Industry",
                description="An industry explicitly named in the filing.",
            ),
            EntityType(
                label="ReportedRevenue",
                description=(
                    "Revenue as reported in a specific fiscal year and context, "
                    "including total and reconciliation rows."
                ),
                properties={
                    "fiscal_year": PropertySpec(type="integer", required=True),
                    "amount_millions": PropertySpec(type="float", required=True),
                    "unit": PropertySpec(
                        type="string", enum=["USD millions"], required=True
                    ),
                    "row_kind": PropertySpec(
                        type="string",
                        enum=["segment", "total", "reconciliation"],
                        required=True,
                    ),
                },
            ),
        ],
        relations=[
            RelationType(
                label="HAS_SEGMENT",
                description=(
                    "The filing identifies a business segment as part of a company."
                ),
                patterns=[("Company", "BusinessSegment")],
            ),
            RelationType(
                label="REPORTS_REVENUE",
                description=(
                    "The filing reports a revenue value for the company or a segment."
                ),
                patterns=[
                    ("Company", "ReportedRevenue"),
                    ("BusinessSegment", "ReportedRevenue"),
                ],
            ),
            RelationType(
                label="EXPOSED_TO_INDUSTRY",
                description=(
                    "The filing explicitly connects a company or segment to an "
                    "industry. Do not infer exposure for other segments."
                ),
                patterns=[("Company", "Industry"), ("BusinessSegment", "Industry")],
            ),
        ],
    )


def _data_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / SOURCE["file_name"]


def _download_pdf() -> Path:
    """Download the pinned report once and reject content that fails its hash."""
    path = _data_path()
    if not path.exists():
        request = urllib.request.Request(
            SOURCE["download_url"],
            headers={"User-Agent": "agentic-graphrag-company-briefing/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except OSError as error:
            raise RuntimeError(
                f"Could not download the pinned report from {SOURCE['download_url']}. "
                "Check network access and retry."
            ) from error
        path.write_bytes(data)

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SOURCE["sha256"]:
        raise ValueError(
            f"The cached report at {path} has SHA-256 {digest}, expected "
            f"{SOURCE['sha256']}. Move that file away and rerun the stage."
        )
    return path


def _report_document() -> Document:
    """Load the verified report and assign its stable graph document key."""
    pdf_path = _download_pdf()
    cache_path = DATA_DIR / "report.document.json"
    if cache_path.exists():
        document = Document.model_validate_json(cache_path.read_text(encoding="utf-8"))
        if (
            document.resolved_document_key != DOCUMENT_KEY
            or document.source_hash != SOURCE["sha256"]
            or document.uri != SOURCE["canonical_source_url"]
        ):
            raise ValueError(
                f"The cached parsed report at {cache_path} "
                "does not match sources.json. "
                "Move that cache file away and rerun the stage."
            )
        return document

    source = SourceRef(
        uri=SOURCE["canonical_source_url"],
        extension=".pdf",
        byte_size=pdf_path.stat().st_size,
        mime_type="application/pdf",
    )
    with pdf_path.open("rb") as stream:
        loaded = next(iter(DoclingPdfLoader().load(source, stream, ReadOptions())))
    values = loaded.model_dump(mode="python")
    values["title"] = SOURCE["title"]
    values["document_key"] = DOCUMENT_KEY
    values["id"] = Document.node_id_for(document_key=DOCUMENT_KEY)
    document = Document.model_validate(values)
    cache_path.write_text(document.model_dump_json(), encoding="utf-8")
    return document


def _derivative_without_risk_paragraph(document: Document) -> Document:
    """Create a demo derivative with the risk passage's paragraph removed."""
    pattern = re.compile(r"\s+".join(map(re.escape, RISK_ANCHOR.split())))
    match = pattern.search(document.text)
    if match is None:
        raise ValueError(
            "The parsed report does not contain the pinned cyclicality passage. "
            "Check the Docling conversion before running source review."
        )
    paragraph_start = document.text.rfind("\n\n", 0, match.start())
    paragraph_start = 0 if paragraph_start < 0 else paragraph_start + 2
    paragraph_end = document.text.find("\n\n", match.end())
    paragraph_end = len(document.text) if paragraph_end < 0 else paragraph_end
    changed = document.text[:paragraph_start] + document.text[paragraph_end:]
    digest = hashlib.sha256(changed.encode("utf-8")).hexdigest()
    section = DocumentSection(
        heading="Demo derivative with one omitted risk paragraph",
        depth=0,
        units=[Unit(kind=UnitKind.PARAGRAPH, text=changed)],
    )
    return Document(
        text=changed,
        title=f"{document.title} (demo derivative)",
        published_at=document.published_at,
        content_date=document.content_date,
        uri=document.uri,
        source_format=SourceFormat.MARKDOWN,
        family=DocumentFamily.PROSE,
        content_hash=digest,
        loader_name="company-briefing-demo-derivative",
        source_hash=digest,
        char_count=len(changed),
        line_count=changed.count("\n"),
        sections=[section],
        document_key=DOCUMENT_KEY,
    )


def _print(value: Any) -> None:
    """Print structured results as readable JSON."""

    def convert(item: Any) -> Any:
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        return str(item)

    print(json.dumps(value, ensure_ascii=False, indent=2, default=convert))


async def _add_document(document: Document) -> AddResult:
    store = build_graph_store("neo4j")
    try:
        graph = await Graph.open(
            schema=_schema(),
            graph_store=store,
            embedder=build_embedder(EMBEDDING_MODEL),
            extraction_settings=ExtractionSettings(mode="gliner"),
            max_llm_pairs=0,
        )
        return await graph.add(documents=[document])
    finally:
        await store.close()


async def prepare() -> None:
    """Verify and add the pinned report to the graph."""
    print(
        f"backend=neo4j project={PROJECT_ID} task={TASK_NAME} document={DOCUMENT_KEY}"
    )
    document = _report_document()
    _print(await _add_document(document))


async def investigate() -> None:
    """Search the graph and run the first built-in agent task invocation."""
    print(f"backend=neo4j project={PROJECT_ID} task={TASK_NAME}")
    store = build_graph_store("neo4j")
    embedder = build_embedder(EMBEDDING_MODEL)
    scope = frozenset({DOCUMENT_KEY})
    try:
        await store.connect()
        companies = await entity_search(
            store,
            embedder,
            "The Boeing Company",
            scope=scope,
            labels=["Company"],
            limit=5,
            mode=EvidenceSearchMode.LEXICAL,
        )
        _print({"company_search": companies})
        if companies.hits:
            graph_view = await explore_relationships(
                store,
                companies.hits[0].entity_id,
                scope=scope,
                relation_types=[
                    "HAS_SEGMENT",
                    "REPORTS_REVENUE",
                    "EXPOSED_TO_INDUSTRY",
                ],
                depth=2,
                max_nodes=50,
                max_edges=100,
            )
            _print({"company_graph": graph_view})

        table = await search_evidence(
            store,
            embedder,
            "Summary of Business Segment Data 2022 revenue total",
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=scope,
        )
        fetched = await fetch_evidence(
            store,
            [hit.evidence_id for hit in table.hits],
            scope=scope,
            max_chars=12_000,
        )
        _print({"revenue_passages": fetched})
        for passage in fetched:
            navigation = await navigate_document_tree(
                store,
                passage.evidence_id,
                NavigationRelation.TABLE_CONTEXT,
                scope=scope,
                limit=12,
                max_chars=12_000,
            )
            if navigation.items:
                _print({"revenue_table_context": navigation})
                break

        agent = build_agent(
            graph_store=store,
            embedder=embedder,
            scope=scope,
            project_id=PROJECT_ID,
            agent_id=AGENT_ID,
            llm_settings=AgentLLMSettings.from_openai_compatible_env(),
            agent_settings=AgentSettings(),
        )
        result = await agent.ainvoke(
            {
                "task_name": TASK_NAME,
                "question": (
                    "Use the FY2022 report to identify every reportable business "
                    "segment, including total and reconciliation rows. Give the "
                    "reported revenue and units. Stop before assessing industry "
                    "risk. Cite the fetched passages and distinguish the fiscal "
                    "year from current conditions."
                ),
            }
        )
        _print({"agent_result": result})
        history = ConversationHistory(store, project_id=PROJECT_ID, agent_id=AGENT_ID)
        _print(await history.list_events(TASK_NAME, limit=200))
        _print(await history.get_task(TASK_NAME))
    finally:
        await store.close()


async def resume() -> None:
    """Resume the same agent task and record a supported decision trace."""
    print(f"backend=neo4j project={PROJECT_ID} task={TASK_NAME}")
    store = build_graph_store("neo4j")
    embedder = build_embedder(EMBEDDING_MODEL)
    scope = frozenset({DOCUMENT_KEY})
    try:
        await store.connect()
        history = ConversationHistory(store, project_id=PROJECT_ID, agent_id=AGENT_ID)
        before = await history.get_task(TASK_NAME)
        _print({"resume_view_before": before})

        agent = build_agent(
            graph_store=store,
            embedder=embedder,
            scope=scope,
            project_id=PROJECT_ID,
            agent_id=AGENT_ID,
            llm_settings=AgentLLMSettings.from_openai_compatible_env(),
            agent_settings=AgentSettings(),
        )
        result = await agent.ainvoke(
            {
                "task_name": TASK_NAME,
                "question": (
                    "Resume the FY2022 briefing. Finish the commercial-airline "
                    "risk section, fetch the exact supporting passages, and cite "
                    "them. Keep the historical scope explicit."
                ),
            }
        )
        _print({"agent_result": result})
        _print({"events_after_resume": await history.list_events(TASK_NAME, limit=200)})
        after = await history.get_task(TASK_NAME)
        _print({"resume_view_after": after})
        if after.view is not None:
            _print(
                {
                    "completed_result_reuse": [
                        {
                            "name": step.name,
                            "validity": step.result_validity,
                        }
                        for steps in after.view.steps.values()
                        for step in steps
                        if step.state.value == "completed"
                    ]
                }
            )

        evidence = await _fetch_support(
            store,
            embedder,
            "significant portion revenues limited number commercial airlines",
            scope,
            expected_text=AIRLINE_REVENUE_ANCHOR,
        )
        decisions = DecisionTraces(store, project_id=PROJECT_ID, agent_id=AGENT_ID)
        recorded = await decisions.record_decision(
            TASK_NAME,
            "briefing.airline-exposure",
            "The FY2022 report identifies a significant share of revenue from "
            "a limited number of commercial airlines.",
            "This report passage establishes commercial-airline exposure but "
            "does not describe current market conditions.",
            supports=[DocumentSupportInput(evidence_id=evidence.evidence_id)],
            fetched_evidence=[evidence],
            assumptions=[
                "This statement describes the FY2022 filing, not current conditions."
            ],
            open_questions=[
                "The filing does not establish present-day market conditions."
            ],
            request_id="company-briefing-airline-exposure-v1",
        )
        if not recorded.recorded or recorded.decision is None:
            raise RuntimeError(f"Could not record the decision: {recorded.error}")
        _print({"decision": recorded.decision})
        _print(await decisions.get_decision(recorded.decision.id))
        _print(await decisions.list_support_history(recorded.decision.id))
    finally:
        await store.close()


async def _fetch_support(
    store: GraphStore,
    embedder: Embedder,
    query: str,
    scope: frozenset[str],
    *,
    expected_text: str | None = None,
) -> FetchOutcome:
    found = await search_evidence(
        store,
        embedder,
        query,
        mode=EvidenceSearchMode.LEXICAL,
        limit=10,
        scope=scope,
    )
    outcomes = await fetch_evidence(
        store,
        [hit.evidence_id for hit in found.hits],
        scope=scope,
        max_chars=12_000,
    )
    normalized = re.sub(r"\s+", " ", expected_text).strip() if expected_text else None
    for outcome in outcomes:
        if outcome.status is not FetchStatus.OK or outcome.text is None:
            continue
        if normalized is None or normalized in re.sub(r"\s+", " ", outcome.text):
            return outcome
    detail = f" containing {expected_text!r}" if expected_text else ""
    raise RuntimeError(f"Could not fetch current evidence{detail}.")


async def review() -> None:
    """Show source-change review and supersede the decision with current support."""
    print(f"backend=neo4j project={PROJECT_ID} task={TASK_NAME}")
    report = _report_document()
    derivative = _derivative_without_risk_paragraph(report)

    store = build_graph_store("neo4j")
    embedder = build_embedder(EMBEDDING_MODEL)
    scope = frozenset({DOCUMENT_KEY})
    try:
        await store.connect()
        decisions = DecisionTraces(store, project_id=PROJECT_ID, agent_id=AGENT_ID)
        page = await decisions.list_decisions(TASK_NAME)
        original = next(
            (
                decision
                for decision in page.page.decisions
                if decision.choice_key == "briefing.airline-exposure"
                and decision.status.value == "active"
            ),
            None,
        )
        if original is None:
            raise RuntimeError("Run the resume stage before source review.")

        _print({"derivative": "one risk paragraph omitted; source report unchanged"})
        _print({"incomplete_source_ingestion": await _add_document(derivative)})
        review_queue = await decisions.list_decisions_for_review(task_name=TASK_NAME)
        _print({"review_after_incomplete_derivative": review_queue})
        if not any(
            decision.id == original.id
            and decision.review_state is ReviewState.NEEDS_REVIEW
            for decision in review_queue.decisions
        ):
            raise RuntimeError(
                "The incomplete source did not flag the decision for review."
            )

        restored = await _add_document(report)
        _print({"restored_pinned_report": restored})
        review_queue = await decisions.list_decisions_for_review(task_name=TASK_NAME)
        _print({"review_after_restoring_source": review_queue})
        current = await _fetch_support(
            store,
            embedder,
            "Historically, the airline industry has been cyclical and very competitive",
            scope,
            expected_text=RISK_ANCHOR,
        )
        result = await decisions.supersede_decision(
            original.id,
            "The FY2022 report describes historical cyclicality in the airline "
            "industry.",
            "Restoring the omitted report paragraph adds direct evidence for "
            "the caveat.",
            explanation=(
                "The earlier working copy omitted a substantive risk paragraph."
            ),
            supports=[DocumentSupportInput(evidence_id=current.evidence_id)],
            fetched_evidence=[current],
            assumptions=["This conclusion is limited to the FY2022 report."],
            request_id=f"company-briefing-airline-exposure-review-{original.id}",
        )
        if not result.recorded or result.decision is None:
            raise RuntimeError(f"Could not supersede the decision: {result.error}")
        _print({"superseding_decision": result.decision})
        _print({"prior_decision": await decisions.get_decision(original.id)})
        _print(
            {"prior_support_history": await decisions.list_support_history(original.id)}
        )
        _print({"current_decision": await decisions.get_decision(result.decision.id)})
        _print(
            {
                "current_support_history": await decisions.list_support_history(
                    result.decision.id
                )
            }
        )
    finally:
        await store.close()


def main(arguments: Sequence[str] | None = None) -> None:
    """Run one stage, or show help without writing to the graph."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        nargs="?",
        choices=("prepare", "investigate", "resume", "review"),
        help="workflow stage; omit to show help",
    )
    options = parser.parse_args(arguments)
    if options.stage is None:
        parser.print_help()
        return
    stages = {
        "prepare": prepare,
        "investigate": investigate,
        "resume": resume,
        "review": review,
    }
    asyncio.run(stages[options.stage]())


if __name__ == "__main__":
    main()
