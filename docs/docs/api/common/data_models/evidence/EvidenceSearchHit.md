---
title: agrag.common.data_models.evidence.EvidenceSearchHit
sidebar_label: EvidenceSearchHit
---

# `agrag.common.data_models.evidence.EvidenceSearchHit` \{#agrag-common-data_models-evidence-EvidenceSearchHit}

Bases: <code>BaseModel</code>

One visible passage found by search.

**Attributes:**

- [**evidence_id**](#agrag-common-data_models-evidence-EvidenceSearchHit-evidence_id) (<code>str</code>) – The evidence id of the passage. Pass it to fetch and
  check_citations.
- [**document_key**](#agrag-common-data_models-evidence-EvidenceSearchHit-document_key) (<code>str</code>) – The key of the document the passage belongs to.
- [**title**](#agrag-common-data_models-evidence-EvidenceSearchHit-title) (<code>str</code>) – The title of that document.
- [**content_hash**](#agrag-common-data_models-evidence-EvidenceSearchHit-content_hash) (<code>str</code>) – The full sha256 content hash of the current version.
- [**location**](#agrag-common-data_models-evidence-EvidenceSearchHit-location) (<code>[EvidenceLocation](EvidenceLocation.md)</code>) – The offsets or pages of the passage. The passage is a whole
  chunk, so the range can be wider than the text that matched.
- [**snippet**](#agrag-common-data_models-evidence-EvidenceSearchHit-snippet) (<code>str</code>) – The first characters of the passage text.
- [**score**](#agrag-common-data_models-evidence-EvidenceSearchHit-score) (<code>float</code>) – An ordering value. Higher scores rank first within one result. A
  score is not a confidence, and it is not a probability that the
  passage supports a claim. Its scale depends on the legs that found
  the passage.
- [**legs**](#agrag-common-data_models-evidence-EvidenceSearchHit-legs) (<code>list\[[EvidenceSearchLeg](EvidenceSearchLeg.md)\]</code>) – The legs that found the passage.

## `content_hash` \{#agrag-common-data_models-evidence-EvidenceSearchHit-content_hash}

```python
content_hash: str
```

## `document_key` \{#agrag-common-data_models-evidence-EvidenceSearchHit-document_key}

```python
document_key: str
```

## `evidence_id` \{#agrag-common-data_models-evidence-EvidenceSearchHit-evidence_id}

```python
evidence_id: str
```

## `legs` \{#agrag-common-data_models-evidence-EvidenceSearchHit-legs}

```python
legs: list[EvidenceSearchLeg]
```

## `location` \{#agrag-common-data_models-evidence-EvidenceSearchHit-location}

```python
location: EvidenceLocation
```

## `score` \{#agrag-common-data_models-evidence-EvidenceSearchHit-score}

```python
score: float
```

## `snippet` \{#agrag-common-data_models-evidence-EvidenceSearchHit-snippet}

```python
snippet: str
```

## `title` \{#agrag-common-data_models-evidence-EvidenceSearchHit-title}

```python
title: str
```
