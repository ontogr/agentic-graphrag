---
title: agrag.common.data_models.evidence.EvidenceKind
sidebar_label: EvidenceKind
---

# `agrag.common.data_models.evidence.EvidenceKind` \{#agrag-common-data_models-evidence-EvidenceKind}

Bases: <code>StrEnum</code>

The two forms of evidence reference.

**Attributes:**

- [**SPAN**](#agrag-common-data_models-evidence-EvidenceKind-SPAN) – A character range of the document text of one version. The range
  is resolved from the chunks of that version.
- [**CHUNK**](#agrag-common-data_models-evidence-EvidenceKind-CHUNK) – One chunk node, for chunks that carry no text offsets.

## `CHUNK` \{#agrag-common-data_models-evidence-EvidenceKind-CHUNK}

```python
CHUNK = 'chunk'
```

## `SPAN` \{#agrag-common-data_models-evidence-EvidenceKind-SPAN}

```python
SPAN = 'span'
```
