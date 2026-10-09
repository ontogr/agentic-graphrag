---
title: agrag.ingestion.resolve.zone_classifier
sidebar_label: zone_classifier
---

# `agrag.ingestion.resolve.zone_classifier` \{#agrag-ingestion-resolve-zone_classifier}

Zone classification for entity-resolution candidate pairs.

**Functions:**

- [**classify_zone**](classify_zone.md) – Assign a candidate pair to a resolution zone.
- [**precluster_ambiguous**](precluster_ambiguous.md) – Find tight ambiguous sub-clusters that can merge without LLM review.
- [**select_llm_pairs**](select_llm_pairs.md) – Rank ambiguous candidates for LLM review, most similar first.

**Attributes:**

- [**DISCARD_THRESHOLD**](DISCARD_THRESHOLD.md) –
- [**FUZZY_FAST_PATH_THRESHOLD**](FUZZY_FAST_PATH_THRESHOLD.md) –
- [**HARD_MERGE_THRESHOLD**](HARD_MERGE_THRESHOLD.md) –
- [**MAX_LLM_PAIRS**](MAX_LLM_PAIRS.md) –
