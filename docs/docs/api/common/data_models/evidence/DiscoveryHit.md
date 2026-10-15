---
title: agrag.common.data_models.evidence.DiscoveryHit
sidebar_label: DiscoveryHit
---

# `agrag.common.data_models.evidence.DiscoveryHit` \{#agrag-common-data_models-evidence-DiscoveryHit}

Bases: <code>BaseModel</code>

One visible passage found by discovery.

**Attributes:**

- [**evidence_id**](#agrag-common-data_models-evidence-DiscoveryHit-evidence_id) (<code>str</code>) – The evidence id of the passage. Pass it to fetch and
  check_citations.
- [**document_key**](#agrag-common-data_models-evidence-DiscoveryHit-document_key) (<code>str</code>) – The key of the document the passage belongs to.
- [**title**](#agrag-common-data_models-evidence-DiscoveryHit-title) (<code>str</code>) – The title of that document.
- [**content_hash**](#agrag-common-data_models-evidence-DiscoveryHit-content_hash) (<code>str</code>) – The full sha256 content hash of the current version.
- [**location**](#agrag-common-data_models-evidence-DiscoveryHit-location) (<code>[EvidenceLocation](EvidenceLocation.md)</code>) – The offsets or pages of the passage. The passage is a whole
  chunk, so the range can be wider than the text that matched.
- [**snippet**](#agrag-common-data_models-evidence-DiscoveryHit-snippet) (<code>str</code>) – The first characters of the passage text.
- [**score**](#agrag-common-data_models-evidence-DiscoveryHit-score) (<code>float</code>) – An ordering value. Higher scores rank first within one result. A
  score is not a confidence, and it is not a probability that the
  passage supports a claim. Its scale depends on the legs that found
  the passage.
- [**legs**](#agrag-common-data_models-evidence-DiscoveryHit-legs) (<code>list\[[DiscoveryLeg](DiscoveryLeg.md)\]</code>) – The legs that found the passage.

## `content_hash` \{#agrag-common-data_models-evidence-DiscoveryHit-content_hash}

```python
content_hash: str
```

## `document_key` \{#agrag-common-data_models-evidence-DiscoveryHit-document_key}

```python
document_key: str
```

## `evidence_id` \{#agrag-common-data_models-evidence-DiscoveryHit-evidence_id}

```python
evidence_id: str
```

## `legs` \{#agrag-common-data_models-evidence-DiscoveryHit-legs}

```python
legs: list[DiscoveryLeg]
```

## `location` \{#agrag-common-data_models-evidence-DiscoveryHit-location}

```python
location: EvidenceLocation
```

## `score` \{#agrag-common-data_models-evidence-DiscoveryHit-score}

```python
score: float
```

## `snippet` \{#agrag-common-data_models-evidence-DiscoveryHit-snippet}

```python
snippet: str
```

## `title` \{#agrag-common-data_models-evidence-DiscoveryHit-title}

```python
title: str
```
