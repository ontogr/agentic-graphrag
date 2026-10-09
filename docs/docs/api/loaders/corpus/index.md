---
title: agrag.loaders.corpus
sidebar_label: corpus
---

# `agrag.loaders.corpus` \{#agrag-loaders-corpus}

The corpus loaders package.

Importing this package registers every core loader with the module-level `registry`
singleton. The docling extra registers itself on top of this when installed.

**Modules:**

- [**base**](base/index.md) – The Loader interface: reads one source and yields Document objects.
- [**decode**](decode/index.md) – The four-step decode pipeline for source bytes.
- [**errors**](errors/index.md) – Errors that the ingestion layer raises.
- [**registry**](registry/index.md) – The extension-to-loader registry.
- [**types**](types/index.md) – Plumbing types for the corpus loaders.
- [**walk**](walk/index.md) – Corpus walk, batching, and resumable streaming.
