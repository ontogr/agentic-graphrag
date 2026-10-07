---
title: agrag.chunking.rules.RuleMatch
sidebar_label: RuleMatch
---

# `agrag.chunking.rules.RuleMatch` \{#agrag-chunking-rules-RuleMatch}

Bases: <code>BaseModel</code>

The documents a rule applies to.

Every key is optional and a key left as `None` matches any value. Keys combine
with AND. A value in a list key matches if it equals any item of the list.

**Attributes:**

- [**loader_names**](#agrag-chunking-rules-RuleMatch-loader_names) (<code>tuple\[str, ...\] | None</code>) – Match `Document.loader_name`.
- [**source_formats**](#agrag-chunking-rules-RuleMatch-source_formats) (<code>tuple\[[SourceFormat](../../common/data_models/document/SourceFormat.md), ...\] | None</code>) – Match `Document.source_format`.
- [**families**](#agrag-chunking-rules-RuleMatch-families) (<code>tuple\[[DocumentFamily](../../common/data_models/document/DocumentFamily.md), ...\] | None</code>) – Match `Document.family`.
- [**uri_glob**](#agrag-chunking-rules-RuleMatch-uri_glob) (<code>str | None</code>) – Match `Document.uri` against this `fnmatch` pattern. Case
  sensitive.

**Functions:**

- [**matches**](#agrag-chunking-rules-RuleMatch-matches) – Return whether every set key matches the document.

## `families` \{#agrag-chunking-rules-RuleMatch-families}

```python
families: tuple[DocumentFamily, ...] | None = None
```

## `loader_names` \{#agrag-chunking-rules-RuleMatch-loader_names}

```python
loader_names: tuple[str, ...] | None = None
```

## `matches` \{#agrag-chunking-rules-RuleMatch-matches}

```python
matches(document:Document) -> bool
```

Return whether every set key matches the document.

## `model_config` \{#agrag-chunking-rules-RuleMatch-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `source_formats` \{#agrag-chunking-rules-RuleMatch-source_formats}

```python
source_formats: tuple[SourceFormat, ...] | None = None
```

## `uri_glob` \{#agrag-chunking-rules-RuleMatch-uri_glob}

```python
uri_glob: str | None = None
```
