---
title: agrag.ingestion.community
sidebar_label: community
---

# `agrag.ingestion.community` \{#agrag-ingestion-community}

Community detection: hierarchical Leiden over the entity graph.

**Classes:**

- [**CommunityDetectionMissingExtraError**](CommunityDetectionMissingExtraError.md) – Raised when graspologic-native is not installed.

**Functions:**

- [**compute_communities**](compute_communities.md) – Run hierarchical Leiden and return level-0 communities.
- [**delete_all_communities**](delete_all_communities.md) – Delete every Community node and its edges, in batches.
- [**detect_communities**](detect_communities.md) – Detect entity communities via hierarchical Leiden.
- [**embed_communities**](embed_communities.md) – Compute each community's embedding from its report text, in place.
- [**fetch_relation_edges**](fetch_relation_edges.md) – Return every live domain relation as a weighted edge tuple.
- [**generate_community_reports**](generate_community_reports.md) – Generate a report for each community, in place.
- [**required_member_ids**](required_member_ids.md) – Return the member ids generate_community_reports will actually read.

**Attributes:**

- [**WeightedEdge**](WeightedEdge.md) – One domain relation as (source_id, target_id, weight, relation_type).
- [**logger**](logger.md) –
