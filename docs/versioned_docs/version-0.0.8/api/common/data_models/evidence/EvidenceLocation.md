---
title: agrag.common.data_models.evidence.EvidenceLocation
sidebar_label: EvidenceLocation
---

# `agrag.common.data_models.evidence.EvidenceLocation` \{#agrag-common-data_models-evidence-EvidenceLocation}

Bases: <code>BaseModel</code>

Where a passage sits in its source.

**Attributes:**

- [**char_start**](#agrag-common-data_models-evidence-EvidenceLocation-char_start) (<code>int | None</code>) – The start offset of the passage text, or None for a passage
  with page provenance.
- [**char_end**](#agrag-common-data_models-evidence-EvidenceLocation-char_end) (<code>int | None</code>) – The exclusive end offset, or None for a passage with page
  provenance.
- [**page_numbers**](#agrag-common-data_models-evidence-EvidenceLocation-page_numbers) (<code>list\[int\]</code>) – The pages of a passage with page provenance. Empty for a
  text passage.

## `char_end` \{#agrag-common-data_models-evidence-EvidenceLocation-char_end}

```python
char_end: int | None = None
```

## `char_start` \{#agrag-common-data_models-evidence-EvidenceLocation-char_start}

```python
char_start: int | None = None
```

## `page_numbers` \{#agrag-common-data_models-evidence-EvidenceLocation-page_numbers}

```python
page_numbers: list[int] = Field(default_factory=list)
```
