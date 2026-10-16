---
title: agrag.loaders.defaults.register_default_loaders
sidebar_label: register_default_loaders
---

# `agrag.loaders.defaults.register_default_loaders` \{#agrag-loaders-defaults-register_default_loaders}

```python
register_default_loaders(target:LoaderRegistry) -> None
```

Register every default loader on a registry.

Docling reads the rich formats and the PDF and image formats. The core readers
keep plain text, XML and the record formats. No extension has two loaders, so
the order of these calls does not change which loader reads a source.

**Parameters:**

- **target** (<code>[LoaderRegistry](../loader_registry/LoaderRegistry.md)</code>) – The registry to fill. Calling this twice on the same registry
  registers the same loaders again and changes nothing.
