---
title: agrag.loaders.types.SourceRef
sidebar_label: SourceRef
---

# `agrag.loaders.types.SourceRef` \{#agrag-loaders-types-SourceRef}

```python
SourceRef(uri:str, extension:str, byte_size:int | None = None, mime_type:str | None = None, modified_at:datetime | None = None) -> None
```

A locatable input, before any bytes are read.

**Attributes:**

- [**uri**](#agrag-loaders-types-SourceRef-uri) (<code>str</code>) – The location of the source, as the caller gave it.
- [**extension**](#agrag-loaders-types-SourceRef-extension) (<code>str</code>) – The lowercased file extension, with its leading dot.
- [**byte_size**](#agrag-loaders-types-SourceRef-byte_size) (<code>int | None</code>) – The size of the source in bytes. `None` when the backend cannot
  cheaply stat the source.
- [**mime_type**](#agrag-loaders-types-SourceRef-mime_type) (<code>str | None</code>) – The detected MIME type, when the loader can detect one.
- [**modified_at**](#agrag-loaders-types-SourceRef-modified_at) (<code>datetime | None</code>) – The last-modified time of the source, when the backend reports it.

## `byte_size` \{#agrag-loaders-types-SourceRef-byte_size}

```python
byte_size: int | None = None
```

## `extension` \{#agrag-loaders-types-SourceRef-extension}

```python
extension: str
```

## `mime_type` \{#agrag-loaders-types-SourceRef-mime_type}

```python
mime_type: str | None = None
```

## `modified_at` \{#agrag-loaders-types-SourceRef-modified_at}

```python
modified_at: datetime | None = None
```

## `uri` \{#agrag-loaders-types-SourceRef-uri}

```python
uri: str
```
