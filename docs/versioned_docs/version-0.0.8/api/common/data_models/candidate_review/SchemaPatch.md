---
title: agrag.common.data_models.candidate_review.SchemaPatch
sidebar_label: SchemaPatch
---

# `agrag.common.data_models.candidate_review.SchemaPatch` \{#agrag-common-data_models-candidate_review-SchemaPatch}

Bases: <code>BaseModel</code>

A deterministic schema change set and its approved candidate ids.

**Attributes:**

- [**readme**](#agrag-common-data_models-candidate_review-SchemaPatch-readme) (<code>str</code>) – Instructions for applying the patch.
- [**patch_format**](#agrag-common-data_models-candidate_review-SchemaPatch-patch_format) (<code>Literal[1]</code>) – Patch format version.
- [**patch_id**](#agrag-common-data_models-candidate_review-SchemaPatch-patch_id) (<code>str</code>) – Stable identifier derived from the base schema and candidates.
- [**created_at**](#agrag-common-data_models-candidate_review-SchemaPatch-created_at) (<code>datetime</code>) – Time the patch was planned.
- [**base_schema**](#agrag-common-data_models-candidate_review-SchemaPatch-base_schema) (<code>[PatchBase](PatchBase.md)</code>) – Schema identity and fingerprint used for planning.
- [**additions**](#agrag-common-data_models-candidate_review-SchemaPatch-additions) (<code>dict\[str, list\[dict\[str, Any\]\]\]</code>) – Entity and relation additions or relation pattern expansions.
- [**add_properties**](#agrag-common-data_models-candidate_review-SchemaPatch-add_properties) (<code>list\[[PatchProperty](PatchProperty.md)\]</code>) – Property definitions to add.
- [**evidence**](#agrag-common-data_models-candidate_review-SchemaPatch-evidence) (<code>dict\[str, int\]</code>) – Aggregate sightings keyed by planned schema change.
- [**candidate_ids**](#agrag-common-data_models-candidate_review-SchemaPatch-candidate_ids) (<code>list\[UUID\]</code>) – Approved candidate ids represented in the patch.

## `add_properties` \{#agrag-common-data_models-candidate_review-SchemaPatch-add_properties}

```python
add_properties: list[PatchProperty] = Field(default_factory=list)
```

## `additions` \{#agrag-common-data_models-candidate_review-SchemaPatch-additions}

```python
additions: dict[str, list[dict[str, Any]]] = Field(default_factory=lambda: {'entities': [], 'relations': []})
```

## `base_schema` \{#agrag-common-data_models-candidate_review-SchemaPatch-base_schema}

```python
base_schema: PatchBase
```

## `candidate_ids` \{#agrag-common-data_models-candidate_review-SchemaPatch-candidate_ids}

```python
candidate_ids: list[UUID] = Field(default_factory=list)
```

## `created_at` \{#agrag-common-data_models-candidate_review-SchemaPatch-created_at}

```python
created_at: datetime
```

## `evidence` \{#agrag-common-data_models-candidate_review-SchemaPatch-evidence}

```python
evidence: dict[str, int] = Field(default_factory=dict)
```

## `patch_format` \{#agrag-common-data_models-candidate_review-SchemaPatch-patch_format}

```python
patch_format: Literal[1] = PATCH_FORMAT
```

## `patch_id` \{#agrag-common-data_models-candidate_review-SchemaPatch-patch_id}

```python
patch_id: str
```

## `readme` \{#agrag-common-data_models-candidate_review-SchemaPatch-readme}

```python
readme: str = PATCH_README
```
