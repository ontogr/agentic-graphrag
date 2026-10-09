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
keep plain text, XML and the record formats, so the precedence of each
extension does not depend on the order of these calls.

**Parameters:**

- **target** (<code>[LoaderRegistry](../loader_registry/LoaderRegistry.md)</code>) – The registry to fill. Registering a loader twice for the same
  extension is a no-op, so calling this twice is safe.
