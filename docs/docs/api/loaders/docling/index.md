---
title: agrag.loaders.docling
sidebar_label: docling
---

# `agrag.loaders.docling` \{#agrag-loaders-docling}

The docling loader package.

Importing this package registers `DoclingLoader` with the corpus registry. The core
loaders win by default for Markdown, HTML, and CSV; docling wins for PDF, DOCX, PPTX,
images, AsciiDoc, and XML.

**Modules:**

- [**loader**](loader/index.md) – Docling-backed loader for PDF, DOCX, PPTX, and image sources.

**Classes:**

- [**DoclingLoader**](loader/DoclingLoader.md) – Reads documents with the docling library.
