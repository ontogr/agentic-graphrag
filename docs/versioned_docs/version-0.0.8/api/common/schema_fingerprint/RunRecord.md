---
title: agrag.common.schema_fingerprint.RunRecord
sidebar_label: RunRecord
---

# `agrag.common.schema_fingerprint.RunRecord` \{#agrag-common-schema_fingerprint-RunRecord}

```python
RunRecord(schema_name:str, schema_version:str, schema_fingerprint:str, extraction_fingerprint:str) -> None
```

What a document and its chunks record about the run that wrote them.

**Attributes:**

- [**schema_name**](#agrag-common-schema_fingerprint-RunRecord-schema_name) (<code>str</code>) – The name of the schema of the run.
- [**schema_version**](#agrag-common-schema_fingerprint-RunRecord-schema_version) (<code>str</code>) – The version string of the schema of the run.
- [**schema_fingerprint**](#agrag-common-schema_fingerprint-RunRecord-schema_fingerprint) (<code>str</code>) – The structure hash of the schema.
- [**extraction_fingerprint**](#agrag-common-schema_fingerprint-RunRecord-extraction_fingerprint) (<code>str</code>) – The hash of descriptions, settings, effective
  mode and LLM inputs.

**Functions:**

- [**stamp**](#agrag-common-schema_fingerprint-RunRecord-stamp) – Return a copy of a document that carries this record.

## `extraction_fingerprint` \{#agrag-common-schema_fingerprint-RunRecord-extraction_fingerprint}

```python
extraction_fingerprint: str
```

## `schema_fingerprint` \{#agrag-common-schema_fingerprint-RunRecord-schema_fingerprint}

```python
schema_fingerprint: str
```

## `schema_name` \{#agrag-common-schema_fingerprint-RunRecord-schema_name}

```python
schema_name: str
```

## `schema_version` \{#agrag-common-schema_fingerprint-RunRecord-schema_version}

```python
schema_version: str
```

## `stamp` \{#agrag-common-schema_fingerprint-RunRecord-stamp}

```python
stamp(document:Document) -> Document
```

Return a copy of a document that carries this record.

**Parameters:**

- **document** (<code>[Document](../data_models/document/Document-ref.md)</code>) – The document to stamp. It is not changed.

**Returns:**

- <code>[Document](../data_models/document/Document-ref.md)</code> – A copy with the four run-record fields set.
