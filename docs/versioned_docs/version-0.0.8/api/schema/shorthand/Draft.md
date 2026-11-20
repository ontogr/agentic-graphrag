---
title: agrag.schema.shorthand.Draft
sidebar_label: Draft
---

# `agrag.schema.shorthand.Draft` \{#agrag-schema-shorthand-Draft}

Bases: <code>NamedTuple</code>

A type read from a source, with the path it was read from.

**Attributes:**

- [**path**](#agrag-schema-shorthand-Draft-path) (<code>str</code>) – The path of the item in the source, for error messages.
- [**body**](#agrag-schema-shorthand-Draft-body) (<code>[JsonObject](JsonObject.md)</code>) – The canonical dict for the item. It may hold `override` and,
  for a relation, `add_patterns`.

## `body` \{#agrag-schema-shorthand-Draft-body}

```python
body: JsonObject
```

## `path` \{#agrag-schema-shorthand-Draft-path}

```python
path: str
```
