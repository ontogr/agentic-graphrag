---
title: agrag.loaders.loader_registry.LoaderRegistry
sidebar_label: LoaderRegistry
---

# `agrag.loaders.loader_registry.LoaderRegistry` \{#agrag-loaders-loader_registry-LoaderRegistry}

```python
LoaderRegistry() -> None
```

Maps each source extension to the one loader that reads it.

**Attributes:**

- **\_by_extension** (<code>dict\[str, [Loader](../base/Loader.md)\]</code>) – The loader for each registered extension.

**Functions:**

- [**for_source**](#agrag-loaders-loader_registry-LoaderRegistry-for_source) – Return the loader for a source's extension.
- [**register**](#agrag-loaders-loader_registry-LoaderRegistry-register) – Add a loader for each extension it claims.

## `for_source` \{#agrag-loaders-loader_registry-LoaderRegistry-for_source}

```python
for_source(source:SourceRef) -> Loader
```

Return the loader for a source's extension.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to find a loader for.

**Returns:**

- <code>[Loader](../base/Loader.md)</code> – The loader registered for the source's extension.

**Raises:**

- <code>[UnsupportedFormatError](../errors/UnsupportedFormatError.md)</code> – No loader claims the source's extension.
- <code>[MissingExtraError](../errors/MissingExtraError.md)</code> – The loader needs a package extra that is not
  installed.

## `register` \{#agrag-loaders-loader_registry-LoaderRegistry-register}

```python
register(loader:Loader) -> None
```

Add a loader for each extension it claims.

Registering a loader of a type that already holds an extension is a no-op,
so calling `register_default_loaders` twice is safe.

**Parameters:**

- **loader** (<code>[Loader](../base/Loader.md)</code>) – The loader to register.

**Raises:**

- <code>ValueError</code> – Another loader type already holds one of the extensions.
