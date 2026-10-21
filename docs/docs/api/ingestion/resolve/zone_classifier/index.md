---
title: agrag.ingestion.resolve.zone_classifier
sidebar_label: zone_classifier
---

# `agrag.ingestion.resolve.zone_classifier` \{#agrag-ingestion-resolve-zone_classifier}

Pair selection and sub-clustering for entity-resolution LLM review.

**Functions:**

- [**name_pair_gate**](name_pair_gate.md) – Return the reason non-exact names cannot merge, or None if allowed.
- [**precluster_ambiguous**](precluster_ambiguous.md) – Find tight ambiguous sub-clusters that can merge without LLM review.
- [**select_llm_pairs**](select_llm_pairs.md) – Rank ambiguous candidates for LLM review and keep the first `max_pairs`.

**Attributes:**

- [**DEFAULT_LLM_CONCURRENCY**](DEFAULT_LLM_CONCURRENCY.md) –
- [**DIGIT_TOKEN_PATTERN**](DIGIT_TOKEN_PATTERN.md) –
- [**DISCARD_THRESHOLD**](DISCARD_THRESHOLD.md) –
- [**HARD_MERGE_THRESHOLD**](HARD_MERGE_THRESHOLD.md) –
- [**LONG_NAME_CHARS**](LONG_NAME_CHARS.md) –
- [**MAX_LLM_PAIRS**](MAX_LLM_PAIRS.md) –
