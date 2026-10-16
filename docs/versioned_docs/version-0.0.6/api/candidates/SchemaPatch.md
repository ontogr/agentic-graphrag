---
title: agrag.candidates.SchemaPatch
sidebar_label: SchemaPatch
---

# `agrag.candidates.SchemaPatch` \{#agrag-candidates-SchemaPatch}

Bases: <code>BaseModel</code>

A deterministic schema change set and its approved candidate ids.

**Attributes:**

- [**readme**](#agrag-candidates-SchemaPatch-readme) (<code>str</code>) – Instructions for applying the patch.
- [**patch_format**](#agrag-candidates-SchemaPatch-patch_format) (<code>Literal[1]</code>) – Patch format version.
- [**patch_id**](#agrag-candidates-SchemaPatch-patch_id) (<code>str</code>) – Stable identifier derived from the base schema and candidates.
- [**created_at**](#agrag-candidates-SchemaPatch-created_at) (<code>datetime</code>) – Time the patch was planned.
- [**base_schema**](#agrag-candidates-SchemaPatch-base_schema) (<code>[PatchBase](../common/data_models/candidate_review/PatchBase.md)</code>) – Schema identity and fingerprint used for planning.
- [**additions**](#agrag-candidates-SchemaPatch-additions) (<code>dict\[str, list\[dict\[str, Any\]\]\]</code>) – Entity and relation additions or relation pattern expansions.
- [**add_properties**](#agrag-candidates-SchemaPatch-add_properties) (<code>list\[[PatchProperty](../common/data_models/candidate_review/PatchProperty.md)\]</code>) – Property definitions to add.
- [**evidence**](#agrag-candidates-SchemaPatch-evidence) (<code>dict\[str, int\]</code>) – Aggregate sightings keyed by planned schema change.
- [**candidate_ids**](#agrag-candidates-SchemaPatch-candidate_ids) (<code>list\[UUID\]</code>) – Approved candidate ids represented in the patch.

## `add_properties` \{#agrag-candidates-SchemaPatch-add_properties}

```python
add_properties: list[PatchProperty] = Field(default_factory=list)
```

## `additions` \{#agrag-candidates-SchemaPatch-additions}

```python
additions: dict[str, list[dict[str, Any]]] = Field(default_factory=lambda: {'entities': [], 'relations': []})
```

## `base_schema` \{#agrag-candidates-SchemaPatch-base_schema}

```python
base_schema: PatchBase
```

## `candidate_ids` \{#agrag-candidates-SchemaPatch-candidate_ids}

```python
candidate_ids: list[UUID] = Field(default_factory=list)
```

## `created_at` \{#agrag-candidates-SchemaPatch-created_at}

```python
created_at: datetime
```

## `evidence` \{#agrag-candidates-SchemaPatch-evidence}

```python
evidence: dict[str, int] = Field(default_factory=dict)
```

## `patch_format` \{#agrag-candidates-SchemaPatch-patch_format}

```python
patch_format: Literal[1] = PATCH_FORMAT
```

## `patch_id` \{#agrag-candidates-SchemaPatch-patch_id}

```python
patch_id: str
```

## `readme` \{#agrag-candidates-SchemaPatch-readme}

```python
readme: str = PATCH_README
```
