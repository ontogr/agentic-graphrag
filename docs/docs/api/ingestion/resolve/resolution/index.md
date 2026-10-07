---
title: agrag.ingestion.resolve.resolution
sidebar_label: resolution
---

# `agrag.ingestion.resolve.resolution` \{#agrag-ingestion-resolve-resolution}

Resolve mentions and persisted entities against the graph.

Ingestion, consolidation, and re-evaluation call the functions here. Each
builds its candidates and neighbor context, runs one `Resolver` pass, and
returns the result.

**Classes:**

- [**BatchResolution**](BatchResolution.md) – The outcome of resolving one batch of mentions.

**Functions:**

- [**find_exact_matches**](find_exact_matches.md) – Return each mention index's matching persisted Entity, if it has one.
- [**resolve_among**](resolve_among.md) – Resolve a fixed set of persisted entities by comparing same-label pairs.
- [**resolve_batch**](resolve_batch.md) – Resolve one extraction batch against itself and the persisted graph.
- [**resolve_persisted**](resolve_persisted.md) – Resolve persisted entities against each other.

**Attributes:**

- [**SYSTEM_RELATION_TYPES**](SYSTEM_RELATION_TYPES.md) –
