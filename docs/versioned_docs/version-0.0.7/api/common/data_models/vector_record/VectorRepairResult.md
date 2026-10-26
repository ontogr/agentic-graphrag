---
title: agrag.common.data_models.vector_record.VectorRepairResult
sidebar_label: VectorRepairResult
---

# `agrag.common.data_models.vector_record.VectorRepairResult` \{#agrag-common-data_models-vector_record-VectorRepairResult}

Bases: <code>BaseModel</code>

Repair outcomes keyed by collection kind.

**Attributes:**

- [**kinds**](#agrag-common-data_models-vector_record-VectorRepairResult-kinds) (<code>dict\[[VectorKind](VectorKind.md), [VectorRepairCounts](VectorRepairCounts.md)\]</code>) – Counts and failures for each requested collection.

## `kinds` \{#agrag-common-data_models-vector_record-VectorRepairResult-kinds}

```python
kinds: dict[VectorKind, VectorRepairCounts] = Field(default_factory=dict)
```
