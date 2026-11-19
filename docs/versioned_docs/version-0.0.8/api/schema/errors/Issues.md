---
title: agrag.schema.errors.Issues
sidebar_label: Issues
---

# `agrag.schema.errors.Issues` \{#agrag-schema-errors-Issues}

```python
Issues() -> None
```

Collects issues so that one load reports every problem.

**Functions:**

- [**add**](#agrag-schema-errors-Issues-add) – Record one issue.
- [**error**](#agrag-schema-errors-Issues-error) – Return the error that reports every collected issue.

**Attributes:**

- [**items**](#agrag-schema-errors-Issues-items) (<code>list\[[SchemaIssue](SchemaIssue.md)\]</code>) –

## `add` \{#agrag-schema-errors-Issues-add}

```python
add(path:str, message:str) -> None
```

Record one issue.

## `error` \{#agrag-schema-errors-Issues-error}

```python
error(source:str | None = None) -> SchemaLoadError
```

Return the error that reports every collected issue.

## `items` \{#agrag-schema-errors-Issues-items}

```python
items: list[SchemaIssue] = []
```
