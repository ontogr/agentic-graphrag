---
title: agrag.common.data_models.evidence.EvidenceSearchMode
sidebar_label: EvidenceSearchMode
---

# `agrag.common.data_models.evidence.EvidenceSearchMode` \{#agrag-common-data_models-evidence-EvidenceSearchMode}

Bases: <code>StrEnum</code>

Which search legs search runs.

**Attributes:**

- [**LEXICAL**](#agrag-common-data_models-evidence-EvidenceSearchMode-LEXICAL) – Full-text search over chunk text.
- [**SEMANTIC**](#agrag-common-data_models-evidence-EvidenceSearchMode-SEMANTIC) – Vector search over chunk embeddings.
- [**HYBRID**](#agrag-common-data_models-evidence-EvidenceSearchMode-HYBRID) – Both legs, fused with reciprocal rank fusion.

## `HYBRID` \{#agrag-common-data_models-evidence-EvidenceSearchMode-HYBRID}

```python
HYBRID = 'hybrid'
```

## `LEXICAL` \{#agrag-common-data_models-evidence-EvidenceSearchMode-LEXICAL}

```python
LEXICAL = 'lexical'
```

## `SEMANTIC` \{#agrag-common-data_models-evidence-EvidenceSearchMode-SEMANTIC}

```python
SEMANTIC = 'semantic'
```
