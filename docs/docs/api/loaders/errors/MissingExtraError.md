---
title: agrag.loaders.errors.MissingExtraError
sidebar_label: MissingExtraError
---

# `agrag.loaders.errors.MissingExtraError` \{#agrag-loaders-errors-MissingExtraError}

```python
MissingExtraError(extension:str, extra:str) -> None
```

Bases: <code>[UnsupportedFormatError](UnsupportedFormatError.md)</code>

A loader exists for this format, but its package extra is not installed.

This class extends `UnsupportedFormatError` on purpose. An error policy can
then treat a missing extra the same way it treats an unsupported format,
instead of always stopping the whole batch.

**Attributes:**

- [**extension**](#agrag-loaders-errors-MissingExtraError-extension) – The file extension that needs the extra.
- [**extra**](#agrag-loaders-errors-MissingExtraError-extra) – The name of the package extra to install.

## `extension` \{#agrag-loaders-errors-MissingExtraError-extension}

```python
extension = extension
```

## `extra` \{#agrag-loaders-errors-MissingExtraError-extra}

```python
extra = extra
```
