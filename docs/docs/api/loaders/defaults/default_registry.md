---
title: agrag.loaders.defaults.default_registry
sidebar_label: default_registry
---

# `agrag.loaders.defaults.default_registry` \{#agrag-loaders-defaults-default_registry}

```python
default_registry() -> LoaderRegistry
```

Return a new registry with every default loader registered.

`agrag.loaders.registry` is the shared instance built by this function.
A bare `LoaderRegistry()` starts empty and rejects every format.
