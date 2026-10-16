---
title: agrag.loaders.walk
sidebar_label: walk
---

# `agrag.loaders.walk` \{#agrag-loaders-walk}

Corpus walk, batching, and resumable streaming.

This module is internal. `Graph.add` uses it to turn a set of sources into batches of
Documents. Only `normalize_inline_text` is for use outside the loaders package, by
`Graph.add`. Nothing else here is a supported interface.

**Functions:**

- [**normalize_inline_text**](normalize_inline_text.md) – Normalize text that a caller passed in memory.
