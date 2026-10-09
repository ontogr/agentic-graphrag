---
title: agrag.loaders.types.JsonMode
sidebar_label: JsonMode
---

# `agrag.loaders.types.JsonMode` \{#agrag-loaders-types-JsonMode}

Bases: <code>StrEnum</code>

How to read a JSON source.

AUTO: Read an array as records and an object as one document.
RECORDS: Read a top-level array as one document per element.
DOCUMENT: Read a top-level array as one document that holds the whole array.

**Attributes:**

- [**AUTO**](#agrag-loaders-types-JsonMode-AUTO) –
- [**DOCUMENT**](#agrag-loaders-types-JsonMode-DOCUMENT) –
- [**RECORDS**](#agrag-loaders-types-JsonMode-RECORDS) –

## `AUTO` \{#agrag-loaders-types-JsonMode-AUTO}

```python
AUTO = 'auto'
```

## `DOCUMENT` \{#agrag-loaders-types-JsonMode-DOCUMENT}

```python
DOCUMENT = 'document'
```

## `RECORDS` \{#agrag-loaders-types-JsonMode-RECORDS}

```python
RECORDS = 'records'
```
