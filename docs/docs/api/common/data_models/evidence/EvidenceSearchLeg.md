---
title: agrag.common.data_models.evidence.EvidenceSearchLeg
sidebar_label: EvidenceSearchLeg
---

# `agrag.common.data_models.evidence.EvidenceSearchLeg` \{#agrag-common-data_models-evidence-EvidenceSearchLeg}

Bases: <code>StrEnum</code>

One search leg that can find a passage.

**Attributes:**

- [**LEXICAL**](#agrag-common-data_models-evidence-EvidenceSearchLeg-LEXICAL) – Full-text search over stored text.
- [**SEMANTIC**](#agrag-common-data_models-evidence-EvidenceSearchLeg-SEMANTIC) – Vector search over stored embeddings.
- [**RERANK**](#agrag-common-data_models-evidence-EvidenceSearchLeg-RERANK) – The cross-encoder stage that reorders fused hits; it appears
  in failures, never in a hit's legs.

## `LEXICAL` \{#agrag-common-data_models-evidence-EvidenceSearchLeg-LEXICAL}

```python
LEXICAL = 'lexical'
```

## `RERANK` \{#agrag-common-data_models-evidence-EvidenceSearchLeg-RERANK}

```python
RERANK = 'rerank'
```

## `SEMANTIC` \{#agrag-common-data_models-evidence-EvidenceSearchLeg-SEMANTIC}

```python
SEMANTIC = 'semantic'
```
