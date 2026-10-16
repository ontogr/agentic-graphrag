---
title: agrag.common.data_models.candidate_review.PatchProperty
sidebar_label: PatchProperty
---

# `agrag.common.data_models.candidate_review.PatchProperty` \{#agrag-common-data_models-candidate_review-PatchProperty}

Bases: <code>BaseModel</code>

Describe a property to add to an entity type.

**Attributes:**

- [**entity**](#agrag-common-data_models-candidate_review-PatchProperty-entity) (<code>str</code>) – Entity label that will own the property.
- [**name**](#agrag-common-data_models-candidate_review-PatchProperty-name) (<code>str</code>) – Property name.
- [**spec**](#agrag-common-data_models-candidate_review-PatchProperty-spec) (<code>dict\[str, Any\]</code>) – Property definition, defaulting to an optional string.

## `entity` \{#agrag-common-data_models-candidate_review-PatchProperty-entity}

```python
entity: str
```

## `name` \{#agrag-common-data_models-candidate_review-PatchProperty-name}

```python
name: str
```

## `spec` \{#agrag-common-data_models-candidate_review-PatchProperty-spec}

```python
spec: dict[str, Any] = Field(default_factory=lambda: {'type': 'string', 'required': False, 'enum': None, 'description': ''})
```
