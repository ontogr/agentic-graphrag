---
title: agrag.chunking.docling
sidebar_label: docling
---

# `agrag.chunking.docling` \{#agrag-chunking-docling}

Docling-native chunking.

This module wraps docling's `HybridChunker` to produce `Chunk` objects with
`PageProvenance`. It imports docling only when it chunks a document, so importing
this module does not require the `docling` extra.

**Classes:**

- [**DoclingChunker**](DoclingChunker.md) – Split a parsed docling document with docling hybrid chunker.
