---
title: agrag.common.data_models.entity_search.SupportingPassage
sidebar_label: SupportingPassage
---

# `agrag.common.data_models.entity_search.SupportingPassage` \{#agrag-common-data_models-entity_search-SupportingPassage}

Bases: <code>BaseModel</code>

A visible passage that supports an entity or a relation.

**Attributes:**

- [**evidence_id**](#agrag-common-data_models-entity_search-SupportingPassage-evidence_id) (<code>str</code>) – The evidence id of the passage. Fetch it to read the text.
- [**document_key**](#agrag-common-data_models-entity_search-SupportingPassage-document_key) (<code>str</code>) – The key of the document the passage belongs to.
- [**location**](#agrag-common-data_models-entity_search-SupportingPassage-location) (<code>[EvidenceLocation](../evidence/EvidenceLocation.md)</code>) – The offsets or pages of the passage.

## `document_key` \{#agrag-common-data_models-entity_search-SupportingPassage-document_key}

```python
document_key: str
```

## `evidence_id` \{#agrag-common-data_models-entity_search-SupportingPassage-evidence_id}

```python
evidence_id: str
```

## `location` \{#agrag-common-data_models-entity_search-SupportingPassage-location}

```python
location: EvidenceLocation
```
