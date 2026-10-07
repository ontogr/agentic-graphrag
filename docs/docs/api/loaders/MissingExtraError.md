---
title: agrag.loaders.MissingExtraError
sidebar_label: MissingExtraError
---

# `agrag.loaders.MissingExtraError` \{#agrag-loaders-MissingExtraError}

```python
MissingExtraError(extension:str, extra:str) -> None
```

Bases: <code>[UnsupportedFormatError](corpus/errors/UnsupportedFormatError.md)</code>

A loader exists for this format, but its package extra is not installed.

This class extends `UnsupportedFormatError` on purpose. An error policy can then
treat
a missing extra the same way it treats an unsupported format, instead of always
stopping
the whole batch.

**Attributes:**

- [**extension**](#agrag-loaders-MissingExtraError-extension) – The file extension that needs the extra.
- [**extra**](#agrag-loaders-MissingExtraError-extra) – The name of the package extra to install.

## `extension` \{#agrag-loaders-MissingExtraError-extension}

```python
extension = extension
```

## `extra` \{#agrag-loaders-MissingExtraError-extra}

```python
extra = extra
```
