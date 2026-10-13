---
title: agrag.common.data_models.graph_record.DeferredWrites
sidebar_label: DeferredWrites
---

# `agrag.common.data_models.graph_record.DeferredWrites` \{#agrag-common-data_models-graph_record-DeferredWrites}

```python
DeferredWrites(entries:list[tuple[str, dict[str, Any]]] = list()) -> None
```

Writes over committed rows, held until the job's commit transaction.

A job may write only rows it created. A write that reaches a committed
row is not applied. The store records it here, and the commit transaction
runs it after the job flips to committed, so a committed row changes
together with the commit and never before. The list lives in the worker
process. A crash before the commit transaction rolls the job back, which
needs nothing from this list, and the commit transaction is atomic.

**Attributes:**

- [**entries**](#agrag-common-data_models-graph_record-DeferredWrites-entries) (<code>list\[tuple\[str, dict\[str, Any\]\]\]</code>) – Each deferred `(query, parameters)` in write order. Order
  matters: a survivor's text replays before its embedding.

**Functions:**

- [**add**](#agrag-common-data_models-graph_record-DeferredWrites-add) – Defer one statement whose parameters already carry no job id.
- [**add_unwritten**](#agrag-common-data_models-graph_record-DeferredWrites-add_unwritten) – Defer the records whose result row says `written` is false.

## `add` \{#agrag-common-data_models-graph_record-DeferredWrites-add}

```python
add(query:str, parameters:Mapping[str, Any]) -> None
```

Defer one statement whose parameters already carry no job id.

## `add_unwritten` \{#agrag-common-data_models-graph_record-DeferredWrites-add_unwritten}

```python
add_unwritten(query:str, records:Sequence[Mapping[str, Any]], rows:Sequence[Mapping[str, Any]], *, require_all:bool = True) -> int
```

Defer the records whose result row says `written` is false.

**Parameters:**

- **query** (<code>str</code>) – The batched write query that produced `rows`.
- **records** (<code>Sequence\[Mapping\[str, Any\]\]</code>) – The `$records` the query ran with.
- **rows** (<code>Sequence\[Mapping\[str, Any\]\]</code>) – The rows it returned, each with `id` and `written`.
- **require_all** (<code>bool</code>) – Whether replay must return one row per record. False
  for writes guarded by a text match, where a missing row means
  the guard failed.

**Returns:**

- <code>int</code> – How many records were deferred.

## `entries` \{#agrag-common-data_models-graph_record-DeferredWrites-entries}

```python
entries: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
```
