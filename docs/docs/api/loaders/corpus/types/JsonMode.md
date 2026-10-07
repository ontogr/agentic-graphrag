---
title: agrag.loaders.corpus.types.JsonMode
sidebar_label: JsonMode
---

# `agrag.loaders.corpus.types.JsonMode` \{#agrag-loaders-corpus-types-JsonMode}

Bases: <code>StrEnum</code>

How to read a JSON source.

AUTO: Read an array as records and an object as one document.
RECORDS: Read a top-level array as one document per element.
DOCUMENT: Read a top-level array as one document that holds the whole array.

**Attributes:**

- [**AUTO**](#agrag-loaders-corpus-types-JsonMode-AUTO) –
- [**DOCUMENT**](#agrag-loaders-corpus-types-JsonMode-DOCUMENT) –
- [**RECORDS**](#agrag-loaders-corpus-types-JsonMode-RECORDS) –

## `AUTO` \{#agrag-loaders-corpus-types-JsonMode-AUTO}

```python
AUTO = 'auto'
```

## `DOCUMENT` \{#agrag-loaders-corpus-types-JsonMode-DOCUMENT}

```python
DOCUMENT = 'document'
```

## `RECORDS` \{#agrag-loaders-corpus-types-JsonMode-RECORDS}

```python
RECORDS = 'records'
```
