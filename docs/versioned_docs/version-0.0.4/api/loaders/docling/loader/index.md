---
title: agrag.loaders.docling.loader
sidebar_label: loader
---

# `agrag.loaders.docling.loader` \{#agrag-loaders-docling-loader}

Docling-backed loader for PDF, DOCX, PPTX, and image sources.

Importing this module does not import the docling library. The loader imports docling
inside `load` so that the rest of the package works without the `docling` extra
installed. The registry raises `MissingExtraError` when a source needs this loader but
the extra is missing.

**Classes:**

- [**DoclingLoader**](DoclingLoader.md) – Reads documents with the docling library.
