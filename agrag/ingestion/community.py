"""Community detection: hierarchical Leiden over the entity graph."""

import asyncio
import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.validation import (
    require_positive_batch_size,
    require_positive_max_concurrency,
)
from agrag.cypher.community_write import delete_communities_batch_query
from agrag.cypher.relations import (
    fetch_all_relations_query,
    fetch_all_relations_query_cursor,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.ingestion.stats import StageFailure
from agrag.loaders.corpus.types import ErrorPolicy


if TYPE_CHECKING:
    from baml_py import ClientRegistry

    from agrag.llm.baml_client.runtime import BamlCallOptions
    from agrag.llm.baml_client.types import CommunityReport


logger = logging.getLogger(__name__)

WeightedEdge = tuple[str, str, float, str]
"""One domain relation as (source_id, target_id, weight, relation_type)."""


class CommunityDetectionMissingExtraError(Exception):
    """Raised when graspologic-native is not installed."""

    def __init__(self, extra: str = "community") -> None:
        """Bind the missing extra's name to the error."""
        super().__init__(
            f"Community detection needs the '{extra}' extra: "
            f"pip install 'agentic-graphrag[{extra}]'"
        )


async def fetch_relation_edges(
    graph_store: GraphStore, *, page_size: int = 5000, use_cursor: bool = True
) -> list[WeightedEdge]:
    """Return every live domain relation as a weighted edge tuple.

    Weight is len(source_chunk_ids) (attestation count). A relation with
    no attested chunks contributes weight 0.0, so an unsupported edge
    cannot inflate clustering or a community's report importance. Two
    entities connected by more than one distinct relation type contribute
    one edge tuple per type; graspologic_native sums parallel-edge
    weights building its own adjacency.

    Supports cursor (keyset) pagination for large graphs where ``SKIP``
    is expensive, and legacy ``SKIP`` pagination for callers that need
    it.

    Args:
        graph_store: Where the relations are read from.
        page_size: Rows fetched per page.
        use_cursor: When True uses keyset pagination on ``(a.id, b.id,
            type(r), r.id)``; when False uses ``SKIP`` pagination.

    Returns:
        Edge tuples as (source_id_str, target_id_str, weight, rel_type).
    """
    edges: list[WeightedEdge] = []
    if use_cursor:
        last_a = ""
        last_b = ""
        last_type = ""
        last_rel_id = ""
        while True:
            rows = await graph_store.execute_read(
                fetch_all_relations_query_cursor(),
                {
                    "last_a": last_a,
                    "last_b": last_b,
                    "last_type": last_type,
                    "last_rel_id": last_rel_id,
                    "limit": page_size,
                },
            )
            if not rows:
                break
            for row in rows:
                scids = row.get("source_chunk_ids") or []
                edges.append(
                    (
                        str(row["source_id"]),
                        str(row["target_id"]),
                        float(len(scids)),
                        str(row["rel_type"]),
                    )
                )
            if len(rows) < page_size:
                break
            last_a = str(rows[-1]["source_id"])
            last_b = str(rows[-1]["target_id"])
            last_type = str(rows[-1]["rel_type"])
            last_rel_id = str(rows[-1]["rel_id"])
        return edges
    skip = 0
    while True:
        rows = await graph_store.execute_read(
            fetch_all_relations_query(), {"skip": skip, "limit": page_size}
        )
        if not rows:
            break
        for row in rows:
            scids = row.get("source_chunk_ids") or []
            edges.append(
                (
                    str(row["source_id"]),
                    str(row["target_id"]),
                    float(len(scids)),
                    str(row["rel_type"]),
                )
            )
        if len(rows) < page_size:
            break
        skip += page_size
    return edges


def compute_communities(
    edges: list[WeightedEdge],
    *,
    max_cluster_size: int = 10,
    resolution: float = 1.0,
    seed: int | None = 0xDEADBEEF,
) -> list[Community]:
    """Run hierarchical Leiden and return level-0 communities.

    CPU-bound and synchronous; callers on the event loop should run this via
    asyncio.to_thread (see Graph._chunk_documents for the same pattern with
    chunking). Only level 0 is kept -- higher levels are computed for
    max_cluster_size capping but never persisted.

    After clustering, one extra pass over the same edge list computes a
    structural-importance signal, entirely from data already in memory --
    no new dependency (graspologic exposes no general centrality function;
    see the follow-up research this refinement is based on), no new query:

    - Each community's internal_weight (total weight of edges where both
       endpoints are its members) -- signal for which communities get a
       real LLM report instead of a heuristic one.
    - Each member's local weight (weight of its own internal edges) --
      used to order member_ids highest-first, so the "most representative"
      members lead the list for both a large qualifying community's
      (token-budget-truncated) LLM prompt and a heuristic report's
      few-name summary.

    Args:
        edges: The weighted edge list from fetch_relation_edges, as
            (source_id, target_id, weight, relation_type) tuples.
        max_cluster_size: The size ceiling a cluster is split past, at every
            level.
        resolution: Leiden's resolution parameter.
        seed: Random seed for reproducibility. None uses the native
            default.

    Returns:
        One Community per level-0 cluster with two or more members, with
        member_ids ordered by local weight descending and internal_weight
        set. Reports (title/summary/rating/findings) are left empty; report
        generation fills them.

    Raises:
        CommunityDetectionMissingExtraError: graspologic-native is not
            installed.
    """
    try:
        import graspologic_native  # noqa: PLC0415
    except ImportError as exc:
        raise CommunityDetectionMissingExtraError from exc

    clusters = graspologic_native.hierarchical_leiden(  # ty: ignore[unresolved-attribute]
        edges=[(source, target, weight) for source, target, weight, _ in edges],
        max_cluster_size=max_cluster_size,
        resolution=resolution,
        seed=seed,
        use_modularity=True,
    )

    cluster_of: dict[str, int] = {c.node: c.cluster for c in clusters if c.level == 0}

    member_weight: dict[str, float] = defaultdict(float)
    community_weight: dict[int, float] = defaultdict(float)
    for source, target, weight, _rel_type in edges:
        source_cluster = cluster_of.get(source)
        target_cluster = cluster_of.get(target)
        if source_cluster is None or target_cluster is None:
            continue
        if source_cluster != target_cluster:
            continue
        community_weight[source_cluster] += weight
        member_weight[source] += weight
        member_weight[target] += weight

    members_by_cluster: dict[int, list[str]] = defaultdict(list)
    for node, cluster in cluster_of.items():
        members_by_cluster[cluster].append(node)

    return [
        Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0.0,
            rating_explanation="",
            member_ids=[
                UUID(n)
                for n in sorted(
                    member_nodes, key=lambda n: member_weight[n], reverse=True
                )
            ],
            internal_weight=community_weight[cluster],
        )
        for cluster, member_nodes in members_by_cluster.items()
        if len(member_nodes) >= 2
    ]


_DEFAULT_DELETE_BATCH_SIZE = 1000


async def delete_all_communities(
    graph_store: GraphStore | GraphStoreTransaction,
    *,
    batch_size: int = _DEFAULT_DELETE_BATCH_SIZE,
) -> None:
    """Delete every Community node and its edges, in batches.

    Repeats the bounded delete until a batch reports fewer than
    batch_size rows deleted.

    Args:
        graph_store: Where the delete runs. Accepts either a
            ``GraphStore`` or a ``GraphStoreTransaction`` handle so a
            caller inside ``store.transaction()`` can delete and rewrite
            communities atomically.
        batch_size: Community nodes deleted per statement.
    """
    require_positive_batch_size(batch_size)
    while True:
        rows = await graph_store.execute_write(
            delete_communities_batch_query(), {"limit": batch_size}
        )
        deleted = rows[0]["deleted"] if rows else 0
        if deleted < batch_size:
            break


_DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT = 5.0
_DEFAULT_REPORT_BATCH_SIZE = 8
_DEFAULT_MAX_MEMBERS_PER_PROMPT = 20
_DEFAULT_MAX_RELATIONS_PER_PROMPT = 20


def _relation_summaries_for(
    community: Community,
    edges: list[WeightedEdge],
    entities_by_id: dict[UUID, Entity],
    *,
    max_relations: int,
) -> list[str]:
    """Return one "source REL_TYPE target" line per internal edge.

    Only edges whose both endpoints are members of the community count.
    An endpoint whose Entity was not hydrated (its name is unknown) drops
    the line rather than showing the LLM a raw UUID. Lines are ordered by
    attestation weight descending, most-attested relations first, and
    truncated to max_relations to bound the batch prompt's token budget.
    """
    member_ids = {str(m) for m in community.member_ids}
    summaries: list[tuple[float, str]] = []
    for source, target, weight, rel_type in edges:
        if source not in member_ids or target not in member_ids:
            continue
        try:
            source_id = UUID(source)
            target_id = UUID(target)
        except ValueError:
            continue
        source_entity = entities_by_id.get(source_id)
        target_entity = entities_by_id.get(target_id)
        if source_entity is None or target_entity is None:
            continue
        summaries.append(
            (weight, f"{source_entity.name} {rel_type} {target_entity.name}")
        )
    summaries.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in summaries[:max_relations]]


def _apply_heuristic_report(
    community: Community, entities_by_id: dict[UUID, Entity]
) -> None:
    """Fill in a cheap, deterministic report with no LLM call.

    Used for communities below min_importance_for_llm_report, and as the
    fallback for any community a batch LLM call did not return a report
    for. member_ids is already ordered by local internal weight descending
    (compute_communities), so the first few really are the community's
    most central, most representative members -- this path is still free
    (no new computation here), it just reuses an ordering already
    produced.
    """
    names = [
        entities_by_id[m].name for m in community.member_ids[:3] if m in entities_by_id
    ]
    community.title = ", ".join(names) or f"Community of {len(community.member_ids)}"
    community.summary = (
        f"A community of {len(community.member_ids)} entities including "
        f"{', '.join(names)}."
    )
    community.rating = min(10.0, community.internal_weight / 2)
    community.rating_explanation = (
        "Rated by internal edge weight; no LLM summary generated."
    )
    community.findings = []


async def generate_community_reports(  # noqa: PLR0915
    communities: list[Community],
    entities_by_id: dict[UUID, Entity],
    *,
    edges: list[WeightedEdge] | None = None,
    min_importance_for_llm_report: float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT,
    batch_size: int = _DEFAULT_REPORT_BATCH_SIZE,
    max_members_per_prompt: int = _DEFAULT_MAX_MEMBERS_PER_PROMPT,
    max_relations_per_prompt: int = _DEFAULT_MAX_RELATIONS_PER_PROMPT,
    max_concurrency: int = 4,
    error_policy: ErrorPolicy = ErrorPolicy.SKIP,
) -> list[StageFailure]:
    """Generate a report for each community, in place.

    Communities at or above min_importance_for_llm_report (internal_weight
    -- total weight of edges internal to the community, set by
    compute_communities) get a real LLM-generated report, batch_size per
    call, bounding total call count at scale. internal_weight, not raw
    member count, decides this: a small but
    densely-attested community can matter more than a larger sparse one.
    Communities below the threshold -- most of a large graph's communities,
    which sit near the max_cluster_size floor -- get
    _apply_heuristic_report's deterministic report instead, no LLM call at
    all.

    A qualifying community's member list is truncated to its top
    max_members_per_prompt members (already ordered by local weight
    descending) before it enters the batch prompt, protecting the batch
    call's token budget from one oversized community without an arbitrary
    cut -- the members dropped are the least central ones. When edges is
    given, each community's prompt also carries its internal
    "source REL_TYPE target" lines (most-attested first, truncated to
    max_relations_per_prompt), so the report can state connections the
    evidence actually attests; a relation whose endpoint Entity was not
    hydrated is omitted.

    When the ``llm`` extra (baml-py) is not installed, qualifying
    communities fall back to the heuristic report too: with ErrorPolicy
    SKIP a warning is logged and the pipeline completes, with RAISE the
    ImportError propagates.

    A batch call failure does not block other batches: it is recorded as
    one StageFailure per community in that batch, each of which then falls
    back to the heuristic report, matching the failure-tolerance shape
    merge.py's description-summarization step already uses. A batch
    response with fewer reports than communities (a malformed or truncated
    response) falls back to the heuristic report for whatever is left over,
    rather than discarding the reports that did come back.

    Args:
        communities: The communities to summarize, mutated in place.
        entities_by_id: Every entity the reports will read, keyed by id,
            for building each community's member-summary context.
        edges: The weighted edge list from fetch_relation_edges, used to
            build each community's attested-relation context. None omits
            relation context from the prompts.
        min_importance_for_llm_report: The internal_weight floor a
            community must meet to get a real LLM report instead of the
            heuristic one.
        batch_size: Communities summarized per LLM call.
        max_members_per_prompt: Members per community fed into the LLM
            prompt, highest-centrality first.
        max_relations_per_prompt: Attested-relation lines per community
            fed into the LLM prompt, most-attested first.
        max_concurrency: Max concurrent SummarizeCommunities calls.
        error_policy: RAISE propagates a batch call failure or a missing
            ``llm`` extra; anything else records it or falls back and
            continues.

    Returns:
        One StageFailure per community whose batch call failed.
    """
    require_positive_batch_size(batch_size)
    require_positive_max_concurrency(max_concurrency)

    llm_candidates = []
    for community in communities:
        if community.internal_weight >= min_importance_for_llm_report:
            llm_candidates.append(community)
        else:
            _apply_heuristic_report(community, entities_by_id)

    failures: list[StageFailure] = []
    if not llm_candidates:
        return failures

    try:
        from agrag.llm.baml_client import b as baml_client  # noqa: PLC0415
        from agrag.llm.baml_client.types import CommunityInput  # noqa: PLC0415
    except ImportError:
        if error_policy is ErrorPolicy.RAISE:
            raise
        logger.warning(
            "The 'llm' extra is not installed; communities fall back to "
            "heuristic reports. Install agentic-graphrag[llm] for "
            "LLM-generated community reports."
        )
        for community in llm_candidates:
            _apply_heuristic_report(community, entities_by_id)
        return failures

    baml_options: BamlCallOptions = {}
    retry = None
    try:
        from agrag.ingestion.extract import ExtractionLLMSettings  # noqa: PLC0415
        from agrag.llm.client_registry import build_client_registry  # noqa: PLC0415
        from agrag.llm.retry import NO_RETRY, call_with_retry  # noqa: PLC0415

        settings = ExtractionLLMSettings.from_openai_compatible_env()
        baml_options["client_registry"] = cast(
            "ClientRegistry",
            build_client_registry(settings.clients, strategy=settings.strategy),
        )
        retry = settings.retry
    except (ImportError, RuntimeError):
        from agrag.llm.retry import NO_RETRY, call_with_retry  # noqa: PLC0415

        retry = NO_RETRY

    relation_context = {
        community.id: _relation_summaries_for(
            community,
            edges or [],
            entities_by_id,
            max_relations=max_relations_per_prompt,
        )
        for community in llm_candidates
    }

    sem = asyncio.Semaphore(max_concurrency)

    async def _batch(batch: list[Community]) -> None:
        async with sem:
            inputs = [
                CommunityInput(
                    entity_summaries=[
                        entities_by_id[m].embedding_text
                        for m in c.member_ids[:max_members_per_prompt]
                        if m in entities_by_id
                    ],
                    relation_summaries=relation_context[c.id],
                )
                for c in batch
            ]
            try:
                summarize = baml_client.SummarizeCommunities
                parameters = inspect.signature(summarize).parameters
                supports_options = "baml_options" in parameters or any(
                    parameter.kind is inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters.values()
                )
                if supports_options:
                    reports = await call_with_retry(
                        lambda: summarize(
                            communities=inputs, baml_options=baml_options
                        ),
                        retry,
                    )
                else:
                    summarize_without_options = cast(
                        "Callable[..., Awaitable[list[CommunityReport]]]", summarize
                    )
                    reports = await call_with_retry(
                        lambda: summarize_without_options(communities=inputs), retry
                    )
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                for community in batch:
                    failures.append(
                        StageFailure(
                            item_id=str(community.id),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                    _apply_heuristic_report(community, entities_by_id)
            else:
                for community, report in zip(batch, reports, strict=False):
                    community.title = report.title
                    community.summary = report.summary
                    # Field(ge=0.0, le=10.0) only validates at construction, not
                    # on this plain attribute assignment, so an out-of-range
                    # LLM rating must be clamped explicitly here.
                    community.rating = max(0.0, min(10.0, report.rating))
                    community.rating_explanation = report.rating_explanation
                    community.findings = report.findings
                for community in batch[len(reports) :]:
                    _apply_heuristic_report(community, entities_by_id)

    batches = [
        llm_candidates[i : i + batch_size]
        for i in range(0, len(llm_candidates), batch_size)
    ]
    await asyncio.gather(*(_batch(b) for b in batches))

    return failures


_DEFAULT_EMBED_BATCH_SIZE = 256


async def embed_communities(
    communities: list[Community],
    *,
    embedder: Embedder,
    batch_size: int = _DEFAULT_EMBED_BATCH_SIZE,
    max_concurrency: int = 4,
) -> list[StageFailure]:
    """Compute each community's embedding from its report text, in place.

    Called after generate_community_reports and before to_node_record(), so
    the vector is already present on the very first (and only) write a
    replace cycle makes.

    Embedder.embed's contract makes no chunking guarantee (see
    agrag/embedding/base.py), so at 1M+ entity scale, where a full recompute
    can produce 100,000+ communities, this batches the embed() calls itself
    rather than passing every community's text in one call.

    A batch embed() failure does not block other batches: it is recorded as
    one StageFailure per community in that batch, matching the
    failure-tolerance shape generate_community_reports already uses. Those
    communities keep embedding=None and still get written by
    Community.to_node_record(), which omits the embedding property when it
    is None, rather than being dropped from the graph.

    Args:
        communities: The communities to embed, mutated in place.
        embedder: Computes one vector per community's embedding_text.
        batch_size: Communities embedded per embed() call.
        max_concurrency: Max concurrent embed calls.

    Returns:
        One StageFailure per community whose batch embed() call failed.
    """
    require_positive_batch_size(batch_size)
    require_positive_max_concurrency(max_concurrency)
    if not communities:
        return []
    sem = asyncio.Semaphore(max_concurrency)
    failures: list[StageFailure] = []

    async def _batch(batch: list[Community]) -> None:
        async with sem:
            try:
                vectors = await embedder.embed([c.embedding_text for c in batch])
            except Exception as exc:  # noqa: BLE001
                for community in batch:
                    failures.append(
                        StageFailure(
                            item_id=str(community.id),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                return
            for community, vector in zip(batch, vectors, strict=True):
                community.embedding = vector

    batches = [
        communities[i : i + batch_size] for i in range(0, len(communities), batch_size)
    ]
    await asyncio.gather(*(_batch(b) for b in batches))
    return failures


def required_member_ids(
    communities: list[Community],
    *,
    min_importance_for_llm_report: float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT,
    max_members_per_prompt: int = _DEFAULT_MAX_MEMBERS_PER_PROMPT,
) -> set[UUID]:
    """Return the member ids generate_community_reports will actually read.

    An LLM-qualifying community only needs its top max_members_per_prompt
    members (already ordered by local weight, highest first); a
    heuristic-report community only needs its top 3. Since level-0
    clusters are capped by max_cluster_size and typically much smaller
    than max_members_per_prompt, this mainly saves by excluding isolated
    entities and any entity type detect_communities() never touches, not
    by truncating within a community.

    Args:
        communities: The communities generate_community_reports will run
            over.
        min_importance_for_llm_report: Must match the value
            generate_community_reports is called with, or the two
            functions disagree about which communities are LLM-qualifying.
        max_members_per_prompt: Must match the value
            generate_community_reports is called with.

    Returns:
        The union of every community's needed member ids.
    """
    needed: set[UUID] = set()
    for community in communities:
        if community.internal_weight >= min_importance_for_llm_report:
            needed.update(community.member_ids[:max_members_per_prompt])
        else:
            needed.update(community.member_ids[:3])
    return needed
