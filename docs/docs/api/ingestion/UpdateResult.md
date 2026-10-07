---
title: agrag.ingestion.UpdateResult
sidebar_label: UpdateResult
---

# `agrag.ingestion.UpdateResult` \{#agrag-ingestion-UpdateResult}

Bases: <code>BaseModel</code>

Summary of an update or soft deletion.

**Attributes:**

- [**document_key**](#agrag-ingestion-UpdateResult-document_key) (<code>str</code>) – Stable identity used for the document node.
- [**no_op**](#agrag-ingestion-UpdateResult-no_op) (<code>bool</code>) – Whether no graph changes were needed.
- [**previous_content_hash**](#agrag-ingestion-UpdateResult-previous_content_hash) (<code>str | None</code>) – Hash stored before the operation, if present.
- [**new_content_hash**](#agrag-ingestion-UpdateResult-new_content_hash) (<code>str | None</code>) – Hash written by an update, or `None` on deletion.
- [**chunks_closed**](#agrag-ingestion-UpdateResult-chunks_closed) (<code>int</code>) – Number of open PART_OF edges closed.
- [**add_result**](#agrag-ingestion-UpdateResult-add_result) (<code>[AddResult](reports/add_result/AddResult.md) | None</code>) – Ingestion details for changed content, if any.

## `add_result` \{#agrag-ingestion-UpdateResult-add_result}

```python
add_result: AddResult | None = None
```

## `chunks_closed` \{#agrag-ingestion-UpdateResult-chunks_closed}

```python
chunks_closed: int = 0
```

## `document_key` \{#agrag-ingestion-UpdateResult-document_key}

```python
document_key: str
```

## `new_content_hash` \{#agrag-ingestion-UpdateResult-new_content_hash}

```python
new_content_hash: str | None = None
```

## `no_op` \{#agrag-ingestion-UpdateResult-no_op}

```python
no_op: bool
```

## `previous_content_hash` \{#agrag-ingestion-UpdateResult-previous_content_hash}

```python
previous_content_hash: str | None = None
```
