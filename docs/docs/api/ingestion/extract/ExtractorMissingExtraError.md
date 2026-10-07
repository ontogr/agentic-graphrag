---
title: agrag.ingestion.extract.ExtractorMissingExtraError
sidebar_label: ExtractorMissingExtraError
---

# `agrag.ingestion.extract.ExtractorMissingExtraError` \{#agrag-ingestion-extract-ExtractorMissingExtraError}

```python
ExtractorMissingExtraError(component:str, extra:str) -> None
```

Bases: <code>[IngestionError](../../loaders/corpus/errors/IngestionError.md)</code>

An Extractor needs a package extra that is not installed.

**Attributes:**

- [**component**](#agrag-ingestion-extract-ExtractorMissingExtraError-component) – The class name that needs the extra.
- [**extra**](#agrag-ingestion-extract-ExtractorMissingExtraError-extra) – The package extra to install.

## `component` \{#agrag-ingestion-extract-ExtractorMissingExtraError-component}

```python
component = component
```

## `extra` \{#agrag-ingestion-extract-ExtractorMissingExtraError-extra}

```python
extra = extra
```
