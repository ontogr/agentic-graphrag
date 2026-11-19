---
title: agrag.schema.errors.SchemaIssue
sidebar_label: SchemaIssue
---

# `agrag.schema.errors.SchemaIssue` \{#agrag-schema-errors-SchemaIssue}

```python
SchemaIssue(path:str, message:str) -> None
```

One problem found in a schema source.

**Attributes:**

- [**path**](#agrag-schema-errors-SchemaIssue-path) (<code>str</code>) – Where the problem is, for example `entities[2].parents`. The
  value `schema` means the whole schema.
- [**message**](#agrag-schema-errors-SchemaIssue-message) (<code>str</code>) – What is wrong and how to fix it.

## `message` \{#agrag-schema-errors-SchemaIssue-message}

```python
message: str
```

## `path` \{#agrag-schema-errors-SchemaIssue-path}

```python
path: str
```
