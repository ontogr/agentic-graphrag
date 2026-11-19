---
title: agrag.ingestion.community.required_member_ids
sidebar_label: required_member_ids
---

# `agrag.ingestion.community.required_member_ids` \{#agrag-ingestion-community-required_member_ids}

```python
required_member_ids(communities:list[Community], *, min_importance_for_llm_report:float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT, max_members_per_prompt:int = _DEFAULT_MAX_MEMBERS_PER_PROMPT) -> set[UUID]
```

Return the member ids generate_community_reports will actually read.

An LLM-qualifying community only needs its top max_members_per_prompt
members (already ordered by local weight, highest first); a
heuristic-report community only needs its top 3. Since level-0
clusters are capped by max_cluster_size and typically much smaller
than max_members_per_prompt, this mainly saves by excluding isolated
entities and any entity type detect_communities() never touches, not
by truncating within a community.

**Parameters:**

- **communities** (<code>list\[[Community](../../common/data_models/community/Community-ref.md)\]</code>) – The communities generate_community_reports will run
  over.
- **min_importance_for_llm_report** (<code>float</code>) – Must match the value
  generate_community_reports is called with, or the two
  functions disagree about which communities are LLM-qualifying.
- **max_members_per_prompt** (<code>int</code>) – Must match the value
  generate_community_reports is called with.

**Returns:**

- <code>set\[UUID\]</code> – The union of every community's needed member ids.
