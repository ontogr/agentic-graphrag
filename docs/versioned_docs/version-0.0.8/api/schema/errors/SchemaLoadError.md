---
title: agrag.schema.errors.SchemaLoadError
sidebar_label: SchemaLoadError
---

# `agrag.schema.errors.SchemaLoadError` \{#agrag-schema-errors-SchemaLoadError}

```python
SchemaLoadError(issues:Sequence[SchemaIssue], *, source:str | None = None) -> None
```

Bases: <code>[SchemaError](SchemaError.md)</code>, <code>ValueError</code>

A schema source is invalid.

The message lists every problem found, one per line, each with the path to
the offending key.

**Attributes:**

- [**issues**](#agrag-schema-errors-SchemaLoadError-issues) – Every problem found.
- [**source**](#agrag-schema-errors-SchemaLoadError-source) – The file path that was read, or `None` for in-memory input.

## `issues` \{#agrag-schema-errors-SchemaLoadError-issues}

```python
issues = tuple(issues)
```

## `source` \{#agrag-schema-errors-SchemaLoadError-source}

```python
source = source
```
