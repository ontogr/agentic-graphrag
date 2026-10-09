---
title: agrag.common.data_models.provenance
sidebar_label: provenance
---

# `agrag.common.data_models.provenance` \{#agrag-common-data_models-provenance}

Provenance types for a chunk.

A chunk's provenance shows where its text came from in the source. The shape of the
provenance depends on which chunker made the chunk.

**Classes:**

- [**BoundingBox**](BoundingBox.md) – A box on a page, in page coordinates.
- [**PageProvenance**](PageProvenance.md) – The location of a chunk across one or more pages.
- [**PageSpan**](PageSpan.md) – One page's part of a chunk.
- [**TextProvenance**](TextProvenance.md) – The location of a chunk inside flattened document text.

**Functions:**

- [**check_page_spans**](check_page_spans.md) – Check that page spans number from 1, have ordered boxes, and are in order.
