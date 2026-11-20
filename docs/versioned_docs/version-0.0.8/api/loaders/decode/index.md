---
title: agrag.loaders.decode
sidebar_label: decode
---

# `agrag.loaders.decode` \{#agrag-loaders-decode}

The four-step decode pipeline for source bytes.

Every text loader shares this pipeline. It runs, in order: encoding detection via
charset-normalizer, byte-order-mark handling, newline normalization, and Unicode
normalization. `ReadOptions.normalization` sets the last three steps. It raises
`DecodeError` on failure rather than silently emitting mojibake.

**Functions:**

- [**decode_text**](decode_text.md) – Decode raw source bytes into normalized text.
