---
title: agrag.loaders.docling.loader
sidebar_label: loader
---

# `agrag.loaders.docling.loader` \{#agrag-loaders-docling-loader}

Docling-backed loaders.

`DoclingLoader` reads the formats that need no model: Markdown, HTML, AsciiDoc, DOCX,
PPTX and XLSX. `DoclingPdfLoader` reads PDF and image files and needs the `docling`
extra. Importing this module does not import the docling library: the loaders import
it when they convert.

**Classes:**

- [**DoclingLoader**](DoclingLoader.md) – Reads Markdown, HTML, AsciiDoc, DOCX, PPTX and XLSX files with docling.
- [**DoclingPdfLoader**](DoclingPdfLoader.md) – Reads PDF and image files with docling.
