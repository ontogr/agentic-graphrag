---
title: agrag.common.data_models.community.Community
sidebar_label: Community
---

# `agrag.common.data_models.community.Community` \{#agrag-common-data_models-community-Community}

Bases: <code>[DataPoint](../data_point/DataPoint.md)</code>

A cluster of entities detected by hierarchical Leiden, with an LLM report.

**Attributes:**

- [**title**](#agrag-common-data_models-community-Community-title) (<code>str</code>) – A short, human-readable name for the community.
- [**summary**](#agrag-common-data_models-community-Community-summary) (<code>str</code>) – A prose summary of what the community is about.
- [**rating**](#agrag-common-data_models-community-Community-rating) (<code>float</code>) – An importance rating for this community, 0-10.
- [**rating_explanation**](#agrag-common-data_models-community-Community-rating_explanation) (<code>str</code>) – One sentence explaining the rating.
- [**findings**](#agrag-common-data_models-community-Community-findings) (<code>list\[str\]</code>) – Distinct factual claims the report supports.
- [**member_ids**](#agrag-common-data_models-community-Community-member_ids) (<code>list\[UUID\]</code>) – Ids of every Entity in this community, ordered by
  internal weighted degree descending (see compute_communities).
  The highest-centrality, most representative members first.
- [**internal_weight**](#agrag-common-data_models-community-Community-internal_weight) (<code>float</code>) – Total weight of edges where both endpoints are
  members of this community. A free-to-compute importance signal
  with no extra query and no new dependency. Used in place of raw
  member count to decide which communities get a real LLM report.
  A small but densely-attested community can matter more than
  a larger sparse one.
- [**embedding**](#agrag-common-data_models-community-Community-embedding) (<code>list\[float\] | None</code>) – The community's dense vector, computed from title and
  summary. None before the report/embedding stage runs.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-community-Community-to_node_record) – Return this community as a GraphStore write record.

## `created_at` \{#agrag-common-data_models-community-Community-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `embedding` \{#agrag-common-data_models-community-Community-embedding}

```python
embedding: list[float] | None = None
```

## `embedding_text` \{#agrag-common-data_models-community-Community-embedding_text}

```python
embedding_text: str
```

Return the text this community's embedding is computed from.

## `findings` \{#agrag-common-data_models-community-Community-findings}

```python
findings: list[str] = Field(default_factory=list)
```

## `id` \{#agrag-common-data_models-community-Community-id}

```python
id: UUID
```

## `internal_weight` \{#agrag-common-data_models-community-Community-internal_weight}

```python
internal_weight: float = Field(default=0.0, ge=0.0)
```

## `member_ids` \{#agrag-common-data_models-community-Community-member_ids}

```python
member_ids: list[UUID] = Field(default_factory=list)
```

## `metadata` \{#agrag-common-data_models-community-Community-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `rating` \{#agrag-common-data_models-community-Community-rating}

```python
rating: float = Field(ge=0.0, le=10.0)
```

## `rating_explanation` \{#agrag-common-data_models-community-Community-rating_explanation}

```python
rating_explanation: str
```

## `summary` \{#agrag-common-data_models-community-Community-summary}

```python
summary: str
```

## `title` \{#agrag-common-data_models-community-Community-title}

```python
title: str
```

## `to_node_record` \{#agrag-common-data_models-community-Community-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this community as a GraphStore write record.
