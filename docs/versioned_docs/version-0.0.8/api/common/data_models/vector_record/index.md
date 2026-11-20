---
title: agrag.common.data_models.vector_record
sidebar_label: vector_record
---

# `agrag.common.data_models.vector_record` \{#agrag-common-data_models-vector_record}

Vector index types shared by the graph store and retrieval.

**Classes:**

- [**CollectionInfo**](CollectionInfo.md) – The dimensions, distance metric and record count of a collection.
- [**Distance**](Distance.md) – A distance metric a vector index compares embeddings with.
- [**VectorHit**](VectorHit.md) – One search result: a matched id, its score, and its stored payload.
- [**VectorKind**](VectorKind.md) – Collections for chunks, raw entities, resolved entities and communities.
- [**VectorRecord**](VectorRecord.md) – An embedding with searchable labels and its exact embedding input.
- [**VectorRepairCounts**](VectorRepairCounts.md) – Repair counts and failures for one collection.
- [**VectorRepairResult**](VectorRepairResult.md) – Repair outcomes keyed by collection kind.
- [**VectorTarget**](VectorTarget.md) – A graph node whose external vector needs synchronization.
- [**VectorWork**](VectorWork.md) – Durable vector synchronization and deletion work after a graph commit.
