---
title: agrag.ingestion.ExtractorMissingExtraError
sidebar_label: ExtractorMissingExtraError
---

# `agrag.ingestion.ExtractorMissingExtraError` \{#agrag-ingestion-ExtractorMissingExtraError}

```python
ExtractorMissingExtraError(component:str, extra:str) -> None
```

Bases: <code>[IngestionError](../loaders/corpus/errors/IngestionError.md)</code>

An Extractor needs a package extra that is not installed.

**Attributes:**

- [**component**](#agrag-ingestion-ExtractorMissingExtraError-component) – The class name that needs the extra.
- [**extra**](#agrag-ingestion-ExtractorMissingExtraError-extra) – The package extra to install.

## `component` \{#agrag-ingestion-ExtractorMissingExtraError-component}

```python
component = component
```

## `extra` \{#agrag-ingestion-ExtractorMissingExtraError-extra}

```python
extra = extra
```
