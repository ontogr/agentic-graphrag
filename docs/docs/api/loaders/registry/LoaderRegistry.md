---
title: agrag.loaders.registry.LoaderRegistry
sidebar_label: LoaderRegistry
---

# `agrag.loaders.registry.LoaderRegistry` \{#agrag-loaders-registry-LoaderRegistry}

```python
LoaderRegistry() -> None
```

Maps a source extension to the loader that reads it.

The registry picks a loader by file extension first. When more than one loader
claims
the same extension, the loader registered with `prefer=True` wins; when several
loaders
are preferred, the last preferred registration wins.

**Attributes:**

- **\_by_extension** (<code>dict\[str, list\[\_Entry\]\]</code>) – The registered loaders for each extension, in registration order.

**Functions:**

- [**for_source**](#agrag-loaders-registry-LoaderRegistry-for_source) – Return the default loader for a source.
- [**register**](#agrag-loaders-registry-LoaderRegistry-register) – Add a loader to the registry.

## `for_source` \{#agrag-loaders-registry-LoaderRegistry-for_source}

```python
for_source(source:SourceRef) -> Loader
```

Return the default loader for a source.

**Parameters:**

- **source** (<code>[SourceRef](../corpus/types/SourceRef.md)</code>) – The source to find a loader for.

**Returns:**

- <code>[Loader](../corpus/base/Loader.md)</code> – The registered loader with the highest precedence for the source's
  extension.

When the top-precedence loader needs a package extra that is not installed,
the first non-preferred loader for the extension whose extra (if any) is
installed is used instead, so an optional loader's absence falls back to the
core reader rather than always failing the source. When no such fallback
exists, the call raises `MissingExtraError`.

**Raises:**

- <code>[UnsupportedFormatError](../corpus/errors/UnsupportedFormatError.md)</code> – No loader claims the source's extension.
- <code>[MissingExtraError](../corpus/errors/MissingExtraError.md)</code> – A loader is mapped to the extension, but its package
  extra failed to import, and no fallback loader is available either.

## `register` \{#agrag-loaders-registry-LoaderRegistry-register}

```python
register(loader:Loader, *, prefer:bool = False, extensions:set[str] | frozenset[str] | None = None) -> None
```

Add a loader to the registry.

Registering the same loader for the same extension more than once is a no-op, so
importing a package that registers loaders repeatedly stays safe.

**Parameters:**

- **loader** (<code>[Loader](../corpus/base/Loader.md)</code>) – The loader to register.
- **prefer** (<code>bool</code>) – Set this to True to make the loader the default for its extensions.
  Leave it False to register the loader only as an explicit, named option.
- **extensions** (<code>set\[str\] | frozenset\[str\] | None</code>) – Only register `loader` for these extensions. Defaults to every
  extension the loader advertises. A caller that wants different
  precedence per
  extension registers the same loader twice with different `extensions`
  sets.
