---
title: agrag.common.data_models.evidence.DiscoveryMode
sidebar_label: DiscoveryMode
---

# `agrag.common.data_models.evidence.DiscoveryMode` \{#agrag-common-data_models-evidence-DiscoveryMode}

Bases: <code>StrEnum</code>

Which search legs discovery runs.

**Attributes:**

- [**LEXICAL**](#agrag-common-data_models-evidence-DiscoveryMode-LEXICAL) – Full-text search over chunk text.
- [**SEMANTIC**](#agrag-common-data_models-evidence-DiscoveryMode-SEMANTIC) – Vector search over chunk embeddings.
- [**HYBRID**](#agrag-common-data_models-evidence-DiscoveryMode-HYBRID) – Both legs, fused with reciprocal rank fusion.

## `HYBRID` \{#agrag-common-data_models-evidence-DiscoveryMode-HYBRID}

```python
HYBRID = 'hybrid'
```

## `LEXICAL` \{#agrag-common-data_models-evidence-DiscoveryMode-LEXICAL}

```python
LEXICAL = 'lexical'
```

## `SEMANTIC` \{#agrag-common-data_models-evidence-DiscoveryMode-SEMANTIC}

```python
SEMANTIC = 'semantic'
```
