---
title: agrag.ingestion.community.generate_community_reports
sidebar_label: generate_community_reports
---

# `agrag.ingestion.community.generate_community_reports` \{#agrag-ingestion-community-generate_community_reports}

```python
generate_community_reports(communities:list[Community], entities_by_id:dict[UUID, Entity], *, edges:list[WeightedEdge] | None = None, min_importance_for_llm_report:float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT, batch_size:int = _DEFAULT_REPORT_BATCH_SIZE, max_members_per_prompt:int = _DEFAULT_MAX_MEMBERS_PER_PROMPT, max_relations_per_prompt:int = _DEFAULT_MAX_RELATIONS_PER_PROMPT, max_concurrency:int = 4, error_policy:ErrorPolicy = ErrorPolicy.SKIP, tracer:Tracer | None = None) -> list[StageFailure]
```

Generate a report for each community, in place.

Communities at or above min_importance_for_llm_report (internal_weight
-- total weight of edges internal to the community, set by
compute_communities) get a real LLM-generated report, batch_size per
call, bounding total call count at scale. internal_weight, not raw
member count, decides this: a small but
densely-attested community can matter more than a larger sparse one.
Communities below the threshold -- most of a large graph's communities,
which sit near the max_cluster_size floor -- get
\_apply_heuristic_report's deterministic report instead, no LLM call at
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
loaded is omitted.

When the `llm` extra (baml-py) is not installed, qualifying
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

**Parameters:**

- **communities** (<code>list\[[Community](../../common/data_models/community/Community-ref.md)\]</code>) – The communities to summarize, mutated in place.
- **entities_by_id** (<code>dict\[UUID, [Entity](../../common/data_models/entity/Entity-ref.md)\]</code>) – Every entity the reports will read, keyed by id,
  for building each community's member-summary context.
- **edges** (<code>list\[[WeightedEdge](WeightedEdge.md)\] | None</code>) – The weighted edge list from fetch_relation_edges, used to
  build each community's attested-relation context. None omits
  relation context from the prompts.
- **min_importance_for_llm_report** (<code>float</code>) – The internal_weight floor a
  community must meet to get a real LLM report instead of the
  heuristic one.
- **batch_size** (<code>int</code>) – Communities summarized per LLM call.
- **max_members_per_prompt** (<code>int</code>) – Members per community fed into the LLM
  prompt, highest-centrality first.
- **max_relations_per_prompt** (<code>int</code>) – Attested-relation lines per community
  fed into the LLM prompt, most-attested first.
- **max_concurrency** (<code>int</code>) – Max concurrent SummarizeCommunities calls.
- **error_policy** (<code>[ErrorPolicy](../../loaders/corpus/types/ErrorPolicy.md)</code>) – RAISE propagates a batch call failure or a missing
  `llm` extra; anything else records it or falls back and
  continues.
- **tracer** (<code>Tracer | None</code>) – Opens one span per batch.

**Returns:**

- <code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code> – One StageFailure per community whose batch call failed.
